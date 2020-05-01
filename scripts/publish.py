#!/usr/bin/env python
import shutil
import os.path
import os
import in_toto.util as util
import in_toto.models.metadata as metadata
import tuf.repository_tool as rtool
import sys
import shlex
import subprocess
import glob

KEYS = './keys'
REPO = './repository'

TUF_ROLES = ['targets', 'layouts', 'packages', 'snapshot', 'timestamp']
IN_TOTO_ROLES = ['alice', 'bob', 'carl']
keys = {x: os.path.join(KEYS, x) for x in IN_TOTO_ROLES}
tuf_keys = {x: util.import_ed25519_publickey_from_file(os.path.join(KEYS, x)) for x in TUF_ROLES}


# Shamelessly copied from upstream
def create_layout(alice_path='../keys/alice',
        bob_path='../keys/bob.pub', carl_path='../keys/carl.pub'):
  # Load Alice's private key to later sign the layout
  key_alice = util.import_ed25519_privatekey_from_file(alice_path)
  # Fetch and load Bob's and Carl's public keys
  # to specify that they are authorized to perform certain step in the layout
  key_bob = util.import_ed25519_publickey_from_file(bob_path)
  key_carl = util.import_ed25519_publickey_from_file(carl_path)

  layout = metadata.Layout.read({
      "_type": "layout",
      "keys": {
          key_bob["keyid"]: key_bob,
          key_carl["keyid"]: key_carl,
      },
      "steps": [{
          "name": "clone",
          "expected_materials": [],
          "expected_products": [["CREATE", "demo-project/foo.py"], ["DISALLOW", "*"]],
          "pubkeys": [key_bob["keyid"]],
          "expected_command": [
              "git",
              "clone",
              "https://github.com/in-toto/demo-project.git"
          ],
          "threshold": 1,
        },{
          "name": "update-version",
          "expected_materials": [["MATCH", "demo-project/*", "WITH", "PRODUCTS",
                                "FROM", "clone"], ["DISALLOW", "*"]],
          "expected_products": [["ALLOW", "demo-project/foo.py"], ["DISALLOW", "*"]],
          "pubkeys": [key_bob["keyid"]],
          "expected_command": [],
          "threshold": 1,
        },{
          "name": "package",
          "expected_materials": [
            ["MATCH", "demo-project/*", "WITH", "PRODUCTS", "FROM",
             "update-version"], ["DISALLOW", "*"],
          ],
          "expected_products": [
              ["CREATE", "demo-project.tar.gz"], ["DISALLOW", "*"],
          ],
          "pubkeys": [key_carl["keyid"]],
          "expected_command": [
              "tar",
              "--exclude",
              ".git",
              "-zcvf",
              "demo-project.tar.gz",
              "demo-project",
          ],
          "threshold": 1,
        }],
      "inspect": [{
          "name": "untar",
          "expected_materials": [
              ["MATCH", "demo-project.tar.gz", "WITH", "PRODUCTS", "FROM", "package"],
              # FIXME: If the routine running inspections would gather the
              # materials/products to record from the rules we wouldn't have to
              # ALLOW other files that we aren't interested in.
              ["ALLOW", ".keep"],
              ["ALLOW", "alice.pub"],
              ["ALLOW", "root.layout"],
              ["DISALLOW", "*"]
          ],
          "expected_products": [
              ["MATCH", "demo-project/foo.py", "WITH", "PRODUCTS", "FROM", "update-version"],
              # FIXME: See expected_materials above
              ["ALLOW", "demo-project/.git/*"],
              ["ALLOW", "demo-project.tar.gz"],
              ["ALLOW", ".keep"],
              ["ALLOW", "alice.pub"],
              ["ALLOW", "root.layout"],
              ["DISALLOW", "*"]
          ],
          "run": [
              "tar",
              "xzf",
              "demo-project.tar.gz",
          ]
        }],
  })

  signed_layout = metadata.Metablock(signed=layout)

  # Sign and dump layout to "root.layout"
  signed_layout.sign(key_alice)
  signed_layout.dump("root.layout")


# create the layout and add it as a tuf target
create_layout(alice_path=keys['alice'],
                   bob_path=keys['bob'] + ".pub",
                   carl_path=keys['carl'] + ".pub")

# by now, we should have a layout lying around, let's move it to our preferred
# location
if not os.path.exists("repository/targets/layouts"):
    os.mkdir("repository/targets/layouts")

# We add our layout to our trusted role now
shutil.move("root.layout", "repository/targets/layouts/root.layout")
repository = rtool.load_repository(REPO)
repository.targets("layouts").add_target("layouts/root.layout")
repository.targets("layouts").load_signing_key(tuf_keys['layouts'])
repository.targets.load_signing_key(tuf_keys['targets'])
repository.snapshot.load_signing_key(tuf_keys['snapshot'])
repository.timestamp.load_signing_key(tuf_keys['timestamp'])
repository.writeall()

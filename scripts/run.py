#!/usr/bin/env python
# This script runs the supply chain and adds the target to tuf
import shutil
import os.path
import os
import in_toto.util as util
import tuf.repository_tool as rtool
import sys
import shlex
import subprocess
import glob
from shutil import copyfile, copytree, rmtree



KEYS = './keys'
REPO = './repository'


IN_TOTO_ROLES = ['alice', 'bob', 'carl']
TUF_ROLES = ['targets', 'layouts', 'packages', 'snapshot', 'timestamp']

keys = {x: os.path.join(KEYS, x) for x in IN_TOTO_ROLES}

if not os.path.exists("repository/targets/packages"):
    os.mkdir("repository/targets/packages")

# now, let's execute our pipeline
def run_pipeline():
  os.chdir('pipeline/owner_alice')
  os.chdir("../functionary_bob")
  clone_cmd = ("in-toto-run"
                    " --verbose"
                    " -t ed25519"
                    " --step-name clone --products demo-project/foo.py"
                    " --key ../../keys/bob -- git clone https://github.com/in-toto/demo-project.git")
  print(clone_cmd)
  subprocess.call(shlex.split(clone_cmd))

  update_version_start_cmd = ("in-toto-record"
                    " start"
                    " --verbose"
                    " -t ed25519"
                    " --step-name update-version"
                    " --key ../../keys/bob"
                    " --materials demo-project/foo.py")

  print(update_version_start_cmd)
  subprocess.call(shlex.split(update_version_start_cmd))

  update_version = "echo 'VERSION = \"foo-v1\"\n\nprint(\"Hello in-toto\")\n' > demo-project/foo.py"
  print(update_version)
  subprocess.call(update_version, shell=True)

  update_version_stop_cmd = ("in-toto-record"
                    " stop"
                    " --verbose"
                    " --step-name update-version"
                    " -t ed25519"
                    " --key ../../keys/bob"
                    " --products demo-project/foo.py")

  print(update_version_stop_cmd)
  subprocess.call(shlex.split(update_version_stop_cmd))

  copytree("demo-project", "../functionary_carl/demo-project")

  os.chdir("../functionary_carl")
  package_cmd = ("in-toto-run"
                 " --verbose"
                 " --step-name package --materials demo-project/foo.py"
                 " --products demo-project.tar.gz"
                 " -t ed25519"
                 " --key ../../keys/carl --record-streams"
                 " -- tar --exclude '.git' -zcvf demo-project.tar.gz demo-project")
  print(package_cmd)
  subprocess.call(shlex.split(package_cmd))

  os.chdir("../..")


# this will have to wait
#  os.chdir("final_product")
#  copyfile("../owner_alice/alice.pub", "alice.pub")
#  verify_cmd = ("in-toto-verify"
#                " --verbose"
#                " --layout root.layout"
#                " --layout-key alice.pub")
# print(verify_cmd)
# retval = subprocess.call(shlex.split(verify_cmd))
# print("Return value: " + str(retval))

run_pipeline()

repository = rtool.load_repository(REPO)

x_in_toto = []
# with the pipeline done, now we want to be able to move 1) our tarball to the
# packages role repository and 2) our links to the layouts role repository
for _file in glob.glob("pipeline/**/*.link"):
    shutil.move(_file, "repository/targets/layouts/")
    targetname = os.path.join('layouts/', os.path.basename(_file))
    repository.targets("layouts").add_target(targetname)
    x_in_toto.append(targetname)

x_in_toto.append("layouts/root.layout")
shutil.move('pipeline/functionary_carl/demo-project.tar.gz', 'repository/targets/packages')

repository.targets("packages").add_target('packages/demo-project.tar.gz', custom={"x-in-toto": x_in_toto})

tuf_keys = {x: util.import_ed25519_publickey_from_file(os.path.join(KEYS, x)) for x in TUF_ROLES}
# now, let's sign all the tuf metadata
repository.targets("packages").load_signing_key(tuf_keys['packages'])
repository.targets("layouts").load_signing_key(tuf_keys['layouts'])
repository.targets.load_signing_key(tuf_keys['targets'])
repository.snapshot.load_signing_key(tuf_keys['snapshot'])
repository.timestamp.load_signing_key(tuf_keys['timestamp'])
repository.writeall()

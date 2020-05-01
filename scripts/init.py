#!/usr/bin/env python
# This script generates keys for all roles and submits them to a keys
# repository. In addition, it will start a vanilla tuf repository with 
# no targets
# It may or may not clean up by itself.
import shutil
import os.path
import os
import subprocess
import in_toto.util as util
import tuf.repository_tool as rtool

KEYS = './keys'
REPO = './repository'
TUF_ROLES = ['root', 'timestamp', 'snapshot', 'targets', 'layouts', 'packages']
IN_TOTO_ROLES = ['alice', 'bob', 'carl']

def cleanup():
    target_dirs = [KEYS, REPO]

    for _dir in target_dirs:
        if os.path.exists(_dir) and os.path.isdir(_dir):
            shutil.rmtree(_dir, True)
        os.mkdir(_dir)

    ## let's also clean the state of our pipeline repository
    os.chdir("pipeline")
    subprocess.call(['git', 'clean', '-xddf'])
    os.chdir("functionary_carl")
    subprocess.call(['rm', '-rf', 'demo-project'])
    os.chdir('..')
    os.chdir('..')

    # finally, let's create the client repository so we can get started
    subprocess.call(['rm', '-rf', 'client'])
    os.mkdir("client")
    os.mkdir("client/metadata")
    os.mkdir("client/metadata/current")
    os.mkdir("client/metadata/previous")



def generate_keys():
    keys = {'tuf': {}, 'in-toto': {}}
    os.chdir(KEYS)
    for role in TUF_ROLES:
        util.generate_and_write_ed25519_keypair(role, password='')
        keys['tuf'][role] = util.import_ed25519_publickey_from_file(role)

    for role in IN_TOTO_ROLES:
        util.generate_and_write_ed25519_keypair(role, password='')
        keys['in-toto'][role] = util.import_ed25519_publickey_from_file(role)
    os.chdir('..')

    return keys



def create_repository(keys):
    repository = rtool.create_new_repository(REPO)

    repository.root.add_verification_key(keys['tuf']['root'])
    repository.root.load_signing_key(keys['tuf']['root'])
    repository.timestamp.add_verification_key(keys['tuf']['timestamp'])
    repository.timestamp.load_signing_key(keys['tuf']['timestamp'])
    repository.snapshot.add_verification_key(keys['tuf']['snapshot'])
    repository.snapshot.load_signing_key(keys['tuf']['snapshot'])
    repository.targets.add_verification_key(keys['tuf']['targets'])
    repository.targets.load_signing_key(keys['tuf']['targets'])

    os.mkdir('repository/targets/layouts')
    repository.targets.delegate('layouts', [keys['tuf']['layouts']], ['layouts/*'])
    repository.targets('layouts').load_signing_key(keys['tuf']['layouts'])

    os.mkdir('repository/targets/packages')
    repository.targets.delegate('packages', [keys['tuf']['packages']], ['packages/*'])
    repository.targets('packages').load_signing_key(keys['tuf']['packages'])
    repository.writeall()
    return repository



cleanup()
keys = generate_keys()
create_repository(keys)

# finally, copy over our original root file so we can bootstrap trust on the client
shutil.copyfile("repository/metadata.staged/1.root.json", "client/metadata/current/root.json")

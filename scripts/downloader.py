#!/usr/bin/env python

import tuf.settings
import tuf.log
import logging
from tuf.client import updater
from in_toto import verifylib
from in_toto.util import import_ed25519_publickey_from_file
from in_toto.models.metadata import Metablock
import os
import shutil
import glob

# we ensure the download always happens by erasing any downloaded stuff
if os.path.exists("in_toto_md"):
    shutil.rmtree("in_toto_md")
os.mkdir("in_toto_md")

tuf.settings.repositories_directory = '.'
client  = updater.Updater('client', 
        repository_mirrors = {'mirror1': {'url_prefix': 'http://localhost:8000',
                                          'metadata_path': 'metadata',
                                          'targets_path': 'targets',
                                          'confined_target_dirs': ['']}}
        )

tuf.log.enable_file_logging() 
tuf.log.add_console_handler()
tuf.log.set_console_log_level(logging.INFO)


print("setting up TUF client...")
target= 'packages/demo-project.tar.gz'
client.refresh()

print("Downloading target package info: {}".format(target))
package_info = client.get_one_valid_targetinfo(target)

# we have a TUF-vetted package now, but we can dive a little bit further back
# now :)
client.download_target(package_info, 'client')
x_in_toto = package_info['fileinfo']['custom']['x-in-toto']
for _target in x_in_toto:
    in_toto_md_info = client.get_one_valid_targetinfo(_target)
    client.download_target(in_toto_md_info, 'client')

# we should be ready for in-toto verification

print("Setting up test hardness for in-toto verification")
alice = import_ed25519_publickey_from_file('./keys/alice.pub')
layout_keys = {x['keyid']: x for x in [alice]}
shutil.copyfile("client/packages/demo-project.tar.gz", "in_toto_md/demo-project.tar.gz")

for _file in glob.glob("client/layouts/*"):
    shutil.copyfile(_file, os.path.join("in_toto_md", os.path.basename(_file)))

os.chdir("in_toto_md")
layout = Metablock.load('root.layout')

# if things are horrible, this will throw a nasty exception. You just wait...
print("Running in-toto verification")
verifylib.in_toto_verify(layout, layout_keys)

# Since it didn't, we can probably copy our target to the main directory
print("Successfully verified with TUF and in-toto!")
shutil.copyfile('in_toto_md/demo-project.tar.gz', 'demo-project.tar.gz')

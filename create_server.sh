#!/bin/bash

cd repository
if [ '!' '-e' 'metadata' ] 
then
    ln -s metadata.staged metadata
fi

python -m http.server

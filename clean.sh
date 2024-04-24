#! /bin/bash

set -e

echo Removing output directory

rm -rf outputDirectory

echo Removing working directory

rm -rf workingDirectory

rm -rf s3Policy*

rm -rf Trust*

clear
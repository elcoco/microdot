#!/usr/bin/env bash

dotdir="$(mktemp -d)"
[[ -z $dotdir ]] && die "Failed to create tmp dir."

microdot="$(dirname $0)/../md -d $dotdir -D "

unencrypted_file="$XDG_CONFIG_HOME/xxx_unencrypted_file.txt"
encrypted_file="$XDG_CONFIG_HOME/xxx_encrypted_file.txt"
unencrypted_dir="$XDG_CONFIG_HOME/xxx_unencrypted_dir"
encrypted_dir="$XDG_CONFIG_HOME/xxx_encrypted_dir"

cmd_init_file_unencrypted="$microdot -i $unencrypted_file"
cmd_init_file_encrypted="$microdot -e -i $encrypted_file"
cmd_init_dir_unencrypted="$microdot -i $unencrypted_dir"
cmd_init_dir_encrypted="$microdot -e -i $encrypted_dir"

function die {
    echo "ERROR: $1"
    exit 1
}

function log {
    echo "[$( date '+%Y-%m-%d %H:%M:%S')] $1"
}

function cleanup() {
    rm -v $unencrypted_file
    rm -rv $unencrypted_dir
    rm -v $encrypted_file
    rm -rv $encrypted_dir

    if [[ -d $dotdir ]] ; then
       rm -rv $dotdir
    fi
}

function print_line() {
    echo '-----------------------------------'
}

function test_init() {
    print_line
    log "$cmd_init_file_unencrypted"
    $cmd_init_file_unencrypted
    print_line

    log "$cmd_init_file_encrypted"
    $cmd_init_file_encrypted
    print_line

    log "$cmd_init_dir_unencrypted"
    $cmd_init_dir_unencrypted
    print_line

    log "$cmd_init_dir_encrypted"
    $cmd_init_dir_encrypted
    print_line

}

echo "$unencrypted_file" > $unencrypted_file
echo "$encrypted_file" > $encrypted_file
mkdir -pv $unencrypted_dir
mkdir -pv $encrypted_dir


test_init



$microdot



if [[ ! -z $1 ]] ; then
    cleanup
    #cleanup
fi

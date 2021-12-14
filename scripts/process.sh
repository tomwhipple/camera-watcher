#!/usr/bin/env bash

# Why can't kerberos launch a Python script?!?

#/etc/opt/kerberosio/scripts/record_kerberos_metadata.py $@

/etc/opt/kerberosio/scripts/watcher.py record_kerberos -d /etc/opt/kerberosio/capture/jsonl $@

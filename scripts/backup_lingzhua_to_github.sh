#!/bin/bash
# Lingzhua -> GitHub backup wrapper
# Delegates to Python script

cd "$(dirname "$0")" || exit 1
exec python3 backup_lingzhua_to_github.py

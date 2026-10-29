#!/usr/bin/env python3
"""Provision a private, revocable Firecrawl Basic-Auth service identity.
Prints only public account names and state; never emits credentials.
"""
import argparse
import fcntl
import os
from pathlib import Path
import re
import secrets
import subprocess
import sys

ROOT = Path("/opt/mad4b/firecrawl-production/auth")
HTPASSWD = ROOT / ".htpasswd"
LOCK = ROOT / ".smoke.lock"  # shared with auth-load-smoke.py
CLIENTS = ROOT / "clients"
NAME_RE = re.compile(r"mad4b-[a-z0-9][a-z0-9-]{2,43}$")

def good_name(value):
    if not NAME_RE.fullmatch(value):
        raise ValueError("invalid account name: require mad4b- and lowercase slug")
    return value

def lines_of(raw):
    return raw.decode("utf-8").splitlines()

def manage(action, name):
    if os.geteuid() != 0:
        raise RuntimeError("root required")
    if not ROOT.is_dir() or ROOT.is_symlink() or not HTPASSWD.is_file() or HTPASSWD.is_symlink():
        raise RuntimeError("credential store not ready")
    if action in ("add", "revoke"): good_name(name)
    CLIENTS.mkdir(mode=0o700, exist_ok=True)
    os.chmod(CLIENTS, 0o700)
    LOCK.touch(mode=0o600, exist_ok=True)
    with LOCK.open("rb") as locker:
        fcntl.flock(locker, fcntl.LOCK_EX)
        with HTPASSWD.open("r+b") as stream:
            fcntl.flock(stream, fcntl.LOCK_EX)
            existing = lines_of(stream.read())
            users = {row.split(":",1)[0] for row in existing if ":" in row}
            if action == "list":
                print("\n".join(sorted(u for u in users if NAME_RE.fullmatch(u))))
                return
            credential = CLIENTS / (name + ".credential")
            if credential.is_symlink():
                raise RuntimeError("credential symlink is forbidden")
            if action == "add":
                if name in users or credential.exists():
                    raise RuntimeError("account already exists")
                password = secrets.token_urlsafe(48)
                digest = subprocess.run(["openssl","passwd","-apr1","-stdin"],
                                        input=password+"\n",text=True,
                                        capture_output=True,check=True).stdout.strip()
                if not digest.startswith("$apr1$"):
                    raise RuntimeError("invalid hash")
                fd = os.open(credential, os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW, 0o600)
                try:
                    with os.fdopen(fd,"w") as out:
                        out.write("username="+name+"\npassword="+password+"\n")
                        out.flush()
                        os.fsync(out.fileno())
                    stream.seek(0,os.SEEK_END)
                    if existing and not existing[-1].endswith("\n"):
                        # Existing credentials must have a terminated final line.
                        stream.seek(0)
                        if not stream.read().endswith(b"\n"):
                            raise RuntimeError("htpasswd must end with newline")
                        stream.seek(0,os.SEEK_END)
                    stream.write((name+":"+digest+"\n").encode("utf-8"))
                    stream.flush()
                    os.fsync(stream.fileno())
                except BaseException:
                    credential.unlink(missing_ok=True)
                    raise
                print("CREATED="+name+" (root-only credential stored; not printed)")
            elif action == "revoke":
                if name not in users:
                    raise RuntimeError("account not found")
                remaining = [row for row in existing if not row.startswith(name+":")]
                stream.seek(0)
                stream.write(("\n".join(remaining)+"\n").encode())
                stream.truncate()
                stream.flush()
                os.fsync(stream.fileno())
                credential.unlink(missing_ok=True)
                print("REVOKED="+name)
            else:
                raise ValueError("invalid action")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action",choices=("add","revoke","list","self-test"))
    parser.add_argument("name",nargs="?")
    args=parser.parse_args()
    if args.action=="self-test":
        for good in ("mad4b-growth-intelligence","mad4b-ops-mon"):
            assert good_name(good)==good
        for bad in ("bad","mad4b-../../other","mad4b-FOO"):
            try: good_name(bad)
            except ValueError: pass
            else: raise AssertionError("invalid account accepted")
        print("consumer-account-self-test: PASS")
        return
    if args.action != "list" and not args.name:
        parser.error("account name required")
    if args.action == "list" and args.name:
        parser.error("list does not accept account name")
    manage(args.action,args.name)
if __name__ == "__main__":
    try: main()
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as e:
        print("FAILED="+type(e).__name__,file=sys.stderr)
        sys.exit(2)

#!/usr/bin/env python3
"""Guard production resolved Compose; no Docker writes or printed secret values."""
import json
import sys

cfg=json.load(sys.stdin)
def gate(ok, message):
    if not ok:
        raise SystemExit("PRODUCTION CONFIG NO-GO: "+message)
gate(cfg.get("name")=="mad4b-firecrawl-production","incorrect project")
svc=cfg.get("services",{})
for name in ("api","playwright-service","nuq-postgres","redis","rabbitmq","gateway"):
    gate(name in svc,"missing "+name)
    x=svc[name]
    gate(x.get("mem_limit") and x.get("cpus"),"unlimited resource "+name)
    gate(not x.get("privileged") and x.get("network_mode")!="host","host access "+name)
    if name != "gateway":
        gate(not x.get("ports"),"direct port publishing "+name)
gate(svc["api"].get("environment",{}).get("ENV")=="production","API not production mode")
import re
gate(not svc["api"].get("build"), "production API must not build on shared VPS")
gate(bool(re.fullmatch(r"ghcr\.io/mad4bdigital-ai/firecrawl-api:sha-[a-f0-9]{40}",svc["api"].get("image",""))),"API image must pin fork GHCR exact source SHA")
gate(svc["api"].get("environment",{}).get("USE_DB_AUTHENTICATION") in ("false", False),"unexpected auth mode")
gate(svc["api"].get("environment",{}).get("ALLOW_LOCAL_WEBHOOKS","").lower()=="false","SSRF guard missing")
gate(not svc["api"].get("extra_hosts"),"host-gateway alias inherited")
gate(svc["api"]["environment"].get("POSTGRES_PASSWORD") not in (None,"","postgres"),"default DB password")
gate(svc["api"]["environment"].get("POSTGRES_PASSWORD")==svc["nuq-postgres"]["environment"].get("POSTGRES_PASSWORD"),"DB secrets differ")
gate((cfg.get("networks",{}).get("backend") or {}).get("internal"),"backend not internal")
gate((cfg.get("networks",{}).get("frontdoor") or {}).get("internal"),"frontdoor not internal")
gate("frontdoor" in svc["api"].get("networks",{}),"API not connected to gateway")
gate("frontdoor" in svc["gateway"].get("networks",{}),"gateway not connected to API")
gate(set(svc["gateway"].get("networks",{}))=={"frontdoor"},"gateway has external access")
gate("egress" not in svc["gateway"].get("networks",{}),"gateway egress enabled")
p=svc["gateway"].get("ports",[])
gate(len(p)==1,"gateway needs exactly one loopback bind")
gate(p[0].get("host_ip") in ("127.0.0.1","::1"),"gateway not loopback")
gate(str(p[0].get("published"))=="13082","unexpected gateway host port")
for name in ("nuq-postgres","redis","rabbitmq"):
    gate("egress" not in svc[name].get("networks",{}),"stateful service egress "+name)
for name in ("foundationdb","foundationdb-init"):
    if name in svc:
        gate("foundationdb-experimental" in svc[name].get("profiles",[]),"foundationDB profile bypass")
for name,target in (("nuq-postgres","/var/lib/postgresql/data"),("redis","/data"),("rabbitmq","/var/lib/rabbitmq")):
    gate(any(v.get("type")=="volume" and v.get("target")==target for v in svc[name].get("volumes",[])),"missing persistent volume "+name)
print("PASS: isolated production Compose, loopback-auth gateway, persistent queue, limits and restricted networks")

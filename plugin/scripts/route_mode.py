#!/usr/bin/env python3
"""Deterministic initial route selection from Simplicio mapper artifacts."""
from __future__ import annotations
import argparse,json,re,sys
from pathlib import Path
from typing import Any,Mapping
SCHEMA="simplicio.route-mode/v1"
ARTIFACTS=("project-map.json","symbol-index.json","call-graph.json")
SENSITIVE=("schema","migration","contract","pyproject.toml","package.json","cargo.toml","go.mod","pom.xml","build.gradle","lock")
TOKEN=re.compile(r"[A-Za-z_][A-Za-z0-9_]{2,}")
class SurveyUnavailable(ValueError): pass
def _norm(value:str)->str: return value.replace("\\","/").strip().lstrip("./").casefold()
def _load(path:Path)->Any:
    try: return json.loads(path.read_text(encoding="utf-8"))
    except (OSError,UnicodeError,ValueError) as exc: raise SurveyUnavailable(str(path)) from exc
def load_survey(map_dir:str|Path)->dict[str,Any]:
    loaded={name:_load(Path(map_dir)/name) for name in ARTIFACTS}; project,symbols,graph=(loaded[name] for name in ARTIFACTS)
    if not isinstance(project,Mapping) or not isinstance(project.get("files"),list): raise SurveyUnavailable("project-map files missing")
    if not isinstance(symbols,Mapping) or not isinstance(symbols.get("symbols"),list): raise SurveyUnavailable("symbol-index symbols missing")
    if not isinstance(graph,Mapping) or not isinstance(graph.get("edges"),list): raise SurveyUnavailable("call-graph edges missing")
    return loaded
def _files(project:Mapping[str,Any])->set[str]:
    return {_norm(row["path"]) for row in project["files"] if isinstance(row,Mapping) and isinstance(row.get("path"),str)}
def resolve_goal_files(goal:str,survey:Mapping[str,Any])->list[str]:
    project,symbols=survey["project-map.json"],survey["symbol-index.json"]; files=_files(project); text=_norm(goal)
    found={path for path in files if path and path in text}; tokens={x.casefold() for x in TOKEN.findall(goal)}
    for row in symbols["symbols"]:
        if not isinstance(row,Mapping): continue
        name=str(row.get("name") or ""); qualified=str(row.get("qualified_name") or ""); defined=row.get("defined_in")
        if not isinstance(defined,str):
            evidence=row.get("evidence"); defined=evidence.get("file") if isinstance(evidence,Mapping) else None
        if isinstance(defined,str) and (name.casefold() in tokens or (qualified and _norm(qualified) in text)):
            path=_norm(defined)
            if path in files: found.add(path)
    return sorted(found)
def fan_in(target_files:list[str],graph:Mapping[str,Any])->int|None:
    if not target_files: return 0
    targets=set(target_files); callers=set()
    for row in graph["edges"]:
        if not isinstance(row,Mapping): continue
        target,source=row.get("target_file"),row.get("source_file")
        if isinstance(target,str) and _norm(target) in targets and isinstance(source,str):
            source=_norm(source)
            if source not in targets: callers.add(source)
    return len(callers)
def sensitive_files(target_files:list[str])->list[str]:
    return sorted(path for path in target_files if any(marker in path for marker in SENSITIVE))
def _result(mode,goal,files,callers,sensitive,survey_available,forced,justification):
    return {"schema":SCHEMA,"mode":mode,"measured":True,"goal":goal,"force_converge":forced,"justification":justification,
            "measurements":{"goal_files":len(files),"resolved_files":files,"fan_in":callers,"sensitive_files":sensitive,
            "sensitive_surface":bool(sensitive),"survey_available":survey_available}}
def decide(root:str|Path,goal:str,*,map_dir:str|Path=".simplicio",force_converge:bool=False)->dict[str,Any]:
    del root
    try: survey=load_survey(map_dir)
    except SurveyUnavailable: return _result("converge",goal,[],None,[],False,force_converge,"goal->0 files, fan-in unknown, survey unavailable; converge fail-closed")
    files=resolve_goal_files(goal,survey); callers=fan_in(files,survey["call-graph.json"]); sensitive=sensitive_files(files); surface="sensitive surface" if sensitive else "no sensitive surface"
    if force_converge: mode="converge"; reason="forced converge; goal->%d file%s, fan-in %s, %s"%(len(files),"" if len(files)==1 else "s","unknown" if callers is None else callers,surface)
    elif not files: mode="converge"; reason="goal->0 files, fan-in 0, no sensitive surface; goal unresolved"
    elif len(files)!=1: mode="converge"; reason="goal->%d files, fan-in %d, %s; multi-file scope"%(len(files),callers,surface)
    elif callers is None or callers>1: mode="converge"; reason="goal->1 file, fan-in %s, %s; hub scope"%("unknown" if callers is None else callers,surface)
    elif sensitive: mode="converge"; reason="goal->1 file, fan-in %d, sensitive surface"%callers
    else: mode="fast-path"; reason="goal->1 file, fan-in %d, no sensitive surface"%callers
    return _result(mode,goal,files,callers,sensitive,True,force_converge,reason)
def record_anchor(anchor_path:str|Path,route:Mapping[str,Any])->bool:
    path=Path(anchor_path)
    if not path.is_file(): return False
    try:
        data=json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data,dict): return False
        data["route_mode"]=dict(route); path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf-8"); return True
    except (OSError,UnicodeError,ValueError): return False
def main(argv:list[str]|None=None)->int:
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument("--root",default="."); parser.add_argument("--goal",required=True)
    parser.add_argument("--map-dir",default=".simplicio"); parser.add_argument("--anchor",default=".simplicio/orchestrator/loop/anchor.json"); parser.add_argument("--force-converge",action="store_true")
    args=parser.parse_args(argv); route=dict(decide(args.root,args.goal,map_dir=args.map_dir,force_converge=args.force_converge)); route["anchor_updated"]=record_anchor(args.anchor,route)
    print(json.dumps(route,ensure_ascii=False,sort_keys=True)); return 0
if __name__=="__main__": sys.exit(main())

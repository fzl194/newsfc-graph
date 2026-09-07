#!/usr/bin/env python3
"""
mml_extract.py — MML 配置文件结构化提取工具

从现网/动网 MML 配置文件中按命令类型、参数名值、正则表达式筛选命令，
输出原始 MML 命令行（保留完整格式，供 Agent 理解命令语法和参数约定）。

内部解析为结构化数据（用于筛选），输出始终为原始 MML 文本。

用法:
  python mml_extract.py -f <config_file> -c "ADD RULE" -p "RULENAME=l_tk.*"
  python mml_extract.py -f <config_file> -c "ADD URR" -p "RG=133"
  python mml_extract.py -f <config_file> -c "ADD URR,ADD URRGROUP" -p "RG=121"
  python mml_extract.py -f <config_file> --stats
  python mml_extract.py -f <config_file> --trace "ffg_tik_ytb"
  python mml_extract.py -f <config_file> --trace "ffg_tik_ytb,ffg_rs,cg_tiktok_shaping"
  python mml_extract.py -f <config_file> --trace "ffg_tik_ytb" --depth 2
"""

import argparse
import json
import os
import pickle
import re
import sys
from collections import OrderedDict

# ─── MML 命令解析 ─────────────────────────────────────────────

# 匹配 MML 命令行: OPERATION OBJNAME:PARAMS;  或  OPERATION OBJNAME;
MML_PATTERN = re.compile(
    r'^(ADD|SET|MOD|RMV|LST|DSP|LCK|ULK|ACT|DEA)\s+'
    r'([A-Za-z0-9_]+)'           # 命令对象名
    r'(?:\s*:\s*(.+?))?\s*;$',    # 参数段（可选）
    re.MULTILINE
)


def parse_mml_line(line):
    """解析单行 MML 命令为结构化 dict。

    Returns:
        dict with keys: cmd, operation, obj, params, raw
        None if line is not a valid MML command
    """
    line = line.strip()
    if not line or line.startswith('//') or line.startswith('#'):
        return None

    m = MML_PATTERN.match(line)
    if not m:
        return None

    operation = m.group(1)
    obj_name = m.group(2)
    params_str = m.group(3)
    params = OrderedDict()

    if params_str:
        parts = _split_params(params_str)
        for part in parts:
            part = part.strip()
            if not part:
                continue
            eq_pos = part.find('=')
            if eq_pos > 0:
                key = part[:eq_pos].strip()
                val = part[eq_pos+1:].strip()
                params[key] = val
            else:
                params[part] = ''

    return {
        'cmd': f'{operation} {obj_name}',
        'operation': operation,
        'obj': obj_name,
        'params': params,
        'raw': line
    }


def _split_params(params_str):
    """按逗号分隔参数，跳过引号内的逗号。"""
    parts = []
    current = []
    in_quote = False
    quote_char = None
    paren_depth = 0

    for ch in params_str:
        if in_quote:
            current.append(ch)
            if ch == quote_char:
                in_quote = False
        elif ch in ('"', "'"):
            in_quote = True
            quote_char = ch
            current.append(ch)
        elif ch == '(':
            paren_depth += 1
            current.append(ch)
        elif ch == ')':
            paren_depth -= 1
            current.append(ch)
        elif ch == ',' and paren_depth == 0:
            parts.append(''.join(current))
            current = []
        else:
            current.append(ch)

    if current:
        parts.append(''.join(current))
    return parts


# ─── 文件解析与缓存 ───────────────────────────────────────────

def parse_file(filepath):
    """解析整个 MML 配置文件，返回所有命令的结构化列表。"""
    commands = []
    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
        for line in f:
            parsed = parse_mml_line(line)
            if parsed:
                commands.append(parsed)
    return commands


def get_cache_path(filepath):
    """生成缓存文件路径。"""
    cache_dir = os.path.join(os.path.dirname(os.path.abspath(filepath)), '.mml_cache')
    os.makedirs(cache_dir, exist_ok=True)
    basename = os.path.basename(filepath)
    return os.path.join(cache_dir, basename + '.pkl')


def load_with_cache(filepath):
    """带缓存的文件解析：首次解析后缓存，文件修改时间变化则自动失效。"""
    cache_path = get_cache_path(filepath)
    file_mtime = os.path.getmtime(filepath)

    if os.path.exists(cache_path):
        try:
            with open(cache_path, 'rb') as f:
                cached = pickle.load(f)
            if cached.get('mtime') == file_mtime:
                return cached['commands']
        except Exception:
            pass

    commands = parse_file(filepath)
    with open(cache_path, 'wb') as f:
        pickle.dump({'mtime': file_mtime, 'commands': commands}, f)
    return commands


# ─── 筛选逻辑 ─────────────────────────────────────────────────

def match_command_type(cmd_info, cmd_patterns):
    """检查命令类型是否匹配任一 pattern（正则，忽略大小写）。"""
    cmd_str = cmd_info['cmd']
    for pattern in cmd_patterns:
        if re.search(pattern, cmd_str, re.IGNORECASE):
            return True
    return False


def match_params(cmd_info, param_filters):
    """检查参数是否满足所有筛选条件（AND 关系）。

    param_filters: list of (param_name_pattern, param_value_pattern) 元组
    参数名和值均支持正则匹配（忽略大小写），值匹配时自动去除引号
    """
    params = cmd_info['params']
    for name_pat, val_pat in param_filters:
        matched = False
        for key, val in params.items():
            if not re.search(name_pat, key, re.IGNORECASE):
                continue
            val_clean = val.strip('"').strip("'")
            if re.search(val_pat, val_clean, re.IGNORECASE):
                matched = True
                break
        if not matched:
            return False
    return True


def filter_commands(commands, cmd_patterns=None, param_filters=None):
    """筛选命令列表。"""
    results = []
    for cmd_info in commands:
        if cmd_patterns and not match_command_type(cmd_info, cmd_patterns):
            continue
        if param_filters and not match_params(cmd_info, param_filters):
            continue
        results.append(cmd_info)
    return results


# ─── 引用追踪 ─────────────────────────────────────────────────

# 常见枚举值，不作为对象引用
_ENUMS = frozenset({
    'ENABLE', 'DISABLE', 'ONLINE', 'OFFLINE', 'VOLUME', 'DURATION',
    'EVENT', 'FREE', 'DEFAULT', 'ANY', 'STRING', 'INHERIT', 'RESPONSE',
    'SINGLE', 'OR', 'AND', 'NOTCONFIG', 'BYTE', 'IP', 'HOSTNAME',
    'LENGTHTYPE', 'UP', 'DOWN', 'NONE', 'NOT', 'USERCONFIG',
    'FLOWFILTER', 'FLOWFILTERGRP', 'PCC', 'BWM', 'HEADEN',
    'SMARTREDIRECT', 'WEBPROXY', 'REMARK_FPI',
})


def _build_obj_name_index(commands):
    """构建全网对象名→定义命令的索引（用于快速查找引用对象定义）。

    Returns:
        dict: {name_clean: [cmd_info, ...]}  同名对象可能有多个定义命令
    """
    index = {}
    for cmd_info in commands:
        for key, val in cmd_info['params'].items():
            val_clean = val.strip('"').strip("'")
            if val_clean and len(val_clean) >= 2 and val_clean.upper() not in _ENUMS:
                index.setdefault(val_clean, []).append(cmd_info)
    return index


def trace_object(commands, object_name, obj_name_index=None):
    """追踪指定对象名的上下游引用（单层）。

    策略:
      - 在所有命令的参数值中搜索该对象名 → "被谁引用"（referenced_by）
      - 从该对象的定义命令中，提取其他参数值中可能的对象名 → "引用了谁"（references）

    Args:
        commands: 全网命令列表
        object_name: 待追踪的对象名
        obj_name_index: 预构建的对象名索引（可选，不传则内部构建）

    Returns:
        dict with 'referenced_by' and 'references' lists of cmd_info
    """
    name_clean = object_name.strip('"').strip("'")

    if obj_name_index is None:
        obj_name_index = _build_obj_name_index(commands)

    # 1. 找引用该对象名的命令（参数值中出现该名，排除自身定义命令）
    referenced_by = []
    # 先找该对象的定义命令，用于排除
    self_defs = set()
    for cmd_info in commands:
        first_param_val = next(iter(cmd_info['params'].values()), '')
        if first_param_val.strip('"').strip("'") == name_clean:
            self_defs.add(id(cmd_info))

    for cmd_info in commands:
        if id(cmd_info) in self_defs:
            continue
        for key, val in cmd_info['params'].items():
            if val.strip('"').strip("'") == name_clean:
                referenced_by.append(cmd_info)
                break

    # 2. 找该对象引用的其他对象（从定义命令的非名参数值中提取）
    references = []
    seen_ref_names = set()
    for cmd_info in obj_name_index.get(name_clean, []):
        for key, val in cmd_info['params'].items():
            val_clean = val.strip('"').strip("'")
            if val_clean == name_clean:
                continue
            if val_clean.upper() in _ENUMS:
                continue
            if val_clean.replace('.', '').replace('-', '').replace(' ', '').isdigit():
                continue
            if len(val_clean) < 2:
                continue
            # 如果该值在全网也作为某对象名存在，则认为是引用
            if val_clean in obj_name_index and val_clean not in seen_ref_names:
                seen_ref_names.add(val_clean)
                # 取该引用对象的定义命令（取第一个即可，避免输出爆炸）
                references.append(obj_name_index[val_clean][0])

    return {
        'referenced_by': referenced_by,
        'references': references
    }


def trace_object_recursive(commands, object_names, depth=1):
    """递归追踪多个对象名的引用链。

    Args:
        commands: 全网命令列表
        object_names: 待追踪的对象名列表（逗号分隔字符串或列表）
        depth: 递归深度（1=仅直接引用，2=引用的引用，...）

    Returns:
        dict: {object_name: {'referenced_by': [...], 'references': [...]}}
              每层引用不会重复追踪已见过的对象（防循环）
    """
    if isinstance(object_names, str):
        object_names = [n.strip() for n in object_names.split(',')]

    obj_name_index = _build_obj_name_index(commands)
    all_results = OrderedDict()
    visited = set()

    current_batch = [n.strip('"').strip("'") for n in object_names]

    for current_depth in range(1, depth + 1):
        next_batch = []
        for name in current_batch:
            if name in visited:
                continue
            visited.add(name)
            trace_result = trace_object(commands, name, obj_name_index)
            all_results[name] = trace_result
            # 收集 references 中发现的新对象名，作为下一层追踪目标
            for ref_cmd in trace_result['references']:
                first_val = next(iter(ref_cmd['params'].values()), '')
                ref_name = first_val.strip('"').strip("'")
                if ref_name and ref_name not in visited and len(ref_name) >= 2:
                    next_batch.append(ref_name)
        current_batch = next_batch
        if not current_batch:
            break

    return all_results


# ─── 统计模式 ─────────────────────────────────────────────────

def stats_mode(commands):
    """输出各命令类型的计数。"""
    counts = OrderedDict()
    for cmd_info in commands:
        cmd = cmd_info['cmd']
        counts[cmd] = counts.get(cmd, 0) + 1
    return counts


# ─── 参数筛选条件解析 ─────────────────────────────────────────

def parse_param_filter(param_str):
    """解析参数筛选条件 'PARAM=VALUE'。

    参数名和值均支持正则匹配。值中的 . * + ? [ ] ( ) | 等均按正则处理。
    若只想精确匹配，使用 ^ 和 $ 锚定，如 -p "RG=^133$"

    Returns:
        (param_name_pattern, param_value_pattern) 元组
    """
    eq_pos = param_str.find('=')
    if eq_pos > 0:
        name = param_str[:eq_pos]
        val = param_str[eq_pos+1:]
        return (name, val)
    # 只有参数名，匹配任意值
    return (param_str, '.*')


# ─── 输出格式化 ───────────────────────────────────────────────

def output_results(results, format_type='raw'):
    """输出筛选结果。始终包含原始 MML 命令行。"""
    if format_type == 'json':
        out = []
        for r in results:
            out.append({
                'cmd': r['cmd'],
                'params': dict(r['params']),
                'raw': r['raw']
            })
        print(json.dumps(out, ensure_ascii=False, indent=2))
    else:
        for r in results:
            print(r['raw'])


def output_trace(trace_result, format_type='raw'):
    """输出单对象引用追踪结果。"""
    print("=== Referenced by (who references this object) ===")
    for r in trace_result['referenced_by']:
        print(r['raw'])
    if not trace_result['referenced_by']:
        print("(none)")
    print()
    print("=== References (what this object references) ===")
    for r in trace_result['references']:
        print(r['raw'])
    if not trace_result['references']:
        print("(none)")


def output_trace_recursive(all_results, format_type='raw'):
    """输出递归引用追踪结果（多对象多层）。"""
    for name, trace_result in all_results.items():
        print(f"{'='*60}")
        print(f"=== Object: {name} ===")
        print(f"{'='*60}")
        output_trace(trace_result, format_type)
        print()


def output_stats(counts):
    """输出统计结果。"""
    for cmd, count in sorted(counts.items()):
        print(f"{cmd}: {count}")


# ─── 主入口 ───────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description='MML 配置文件结构化提取工具（输出原始 MML 命令行）',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=r"""
示例:
  %(prog)s -f live.txt -c "ADD RULE"
  %(prog)s -f live.txt -c "ADD RULE" -p "RULENAME=l_tk.*"
  %(prog)s -f live.txt -c "ADD URR" -p "RG=133"
  %(prog)s -f live.txt -c "ADD URR,ADD URRGROUP" -p "RG=121"
  %(prog)s -f live.txt -c "ADD FLOWFILTERGRP" -p "FLWFLTRGRPNAME=ffg_rs"
  %(prog)s -f live.txt --stats
  %(prog)s -f live.txt --trace "ffg_tik_ytb"
  %(prog)s -f live.txt --trace "ffg_tik_ytb,ffg_rs,cg_tiktok_shaping"
  %(prog)s -f live.txt --trace "ffg_tik_ytb" --depth 2
  %(prog)s -f live.txt -c "ADD RULE" --format json

参数筛选支持正则（参数名和值均支持）:
  -p "RULENAME=l_tk.*"        值正则匹配（l_tk 开头的规则名）
  -p "RG=\d{3}"              值正则匹配（3位数字的 RG）
  -p "RULENAME=.*nu.*"        值正则匹配（含 nu 的规则名）
  多个 -p 为 AND 关系:
  -p "RG=121" -p "USAGERPTMODE=OFFLINE"

引用追踪:
  --trace "obj1"              追踪单个对象的上下游引用（1层）
  --trace "obj1,obj2,obj3"    批量追踪多个对象（1层）
  --trace "obj1" --depth 3    递归追踪，沿 references 方向展开到第3层
  depth=1 等同于旧版 --trace（仅直接引用）
  depth>1 会自动对 references 发现的对象继续追踪，已访问的对象不会重复
"""
    )
    parser.add_argument('-f', '--file', required=True,
                        help='MML 配置文件路径')
    parser.add_argument('-c', '--command', default=None,
                        help='命令类型筛选，支持逗号分隔多类型，支持正则 (如 "ADD RULE" 或 "ADD URR,ADD URRGROUP" 或 "ADD.*")')
    parser.add_argument('-p', '--param', action='append', default=[],
                        help='参数筛选，格式 PARAM=VALUE（均支持正则），支持多次 -p (AND 关系)')
    parser.add_argument('--stats', action='store_true',
                        help='统计模式：输出各命令类型的计数')
    parser.add_argument('--trace', default=None, metavar='OBJECT_NAMES',
                        help='引用追踪：给定对象名，追踪其上下游引用。支持逗号分隔多个对象名')
    parser.add_argument('--depth', type=int, default=1,
                        help='递归追踪深度（默认1=仅直接引用，2+=沿references方向递归展开）')
    parser.add_argument('--format', choices=['raw', 'json'], default='raw',
                        help='输出格式：raw(原始 MML 行，默认) / json(含结构化信息)')
    parser.add_argument('--no-cache', action='store_true',
                        help='禁用缓存，强制重新解析')

    args = parser.parse_args()

    # 解析文件（带缓存）
    if args.no_cache:
        commands = parse_file(args.file)
    else:
        commands = load_with_cache(args.file)

    # 统计模式
    if args.stats:
        counts = stats_mode(commands)
        output_stats(counts)
        return

    # 引用追踪模式
    if args.trace:
        if args.depth > 1 or ',' in args.trace:
            # 多对象或递归追踪
            all_results = trace_object_recursive(commands, args.trace, depth=args.depth)
            output_trace_recursive(all_results, args.format)
        else:
            # 单对象单层（兼容旧版行为）
            trace_result = trace_object(commands, args.trace)
            output_trace(trace_result, args.format)
        return

    # 常规筛选模式
    cmd_patterns = None
    if args.command:
        cmd_patterns = [c.strip() for c in args.command.split(',')]

    param_filters = []
    for p in args.param:
        param_filters.append(parse_param_filter(p))

    results = filter_commands(commands, cmd_patterns, param_filters if param_filters else None)
    output_results(results, args.format)


if __name__ == '__main__':
    main()

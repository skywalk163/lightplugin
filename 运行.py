# -*- coding: utf-8 -*-
"""
lightplugin 运行器
==================
在 lightplugin 项目内用「光明」编译器编译并运行 .light 程序。

与 lightharness/运行.py 的区别：插件要能「跨域」导入宿主模块
（`从 工具 导入 造工具定义`、`从 toolcordis 导入 绳装配` 等），
所以搜索路径在「本插件目录 + 项目根」之外，还要带上 lightharness 的 src 与自包含 stdlib。

用法:
    python 运行.py 插件/异步作业轮询/异步作业轮询.light [参数...]
    python 运行.py 插件/异步作业轮询/测试_异步作业轮询.light

环境变量:
    LIGHT_MERGE     光明编译器（语言本体）路径，默认 G:\\dswork\\duan-light-merge\\light-merge
    LIGHTHARNESS    宿主项目路径，默认 G:\\dswork\\duan-light-merge\\lightharness
    HARNESS_ROOT    工具可见的项目根（安全沙箱根），默认宿主项目路径
"""
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
PLUGINS = os.path.join(ROOT, '插件')

LIGHT_MERGE = os.environ.get('LIGHT_MERGE', r'G:\dswork\duan-light-merge\light-merge')
LIGHTHARNESS = os.environ.get('LIGHTHARNESS', r'G:\dswork\duan-light-merge\lightharness')

LH_SRC = os.path.join(LIGHTHARNESS, 'src')
LH_STDLIB = os.path.join(LIGHTHARNESS, 'stdlib')

for _label, _p in (('光明编译器', LIGHT_MERGE), ('宿主项目', LIGHTHARNESS)):
    if not os.path.isdir(_p):
        print('错误: 找不到%s（%s）' % (_label, _p))
        sys.exit(1)


def _plugin_search_dirs():
    """每个插件的一级目录都要入搜索路径 —— 否则插件之间无法互导
    （例：图片生成 要 `从 异步作业轮询 导入 提交作业`）。"""
    dirs = []
    if os.path.isdir(PLUGINS):
        for name in sorted(os.listdir(PLUGINS)):
            p = os.path.join(PLUGINS, name)
            if os.path.isdir(p) and not name.startswith(('_', '.')):
                dirs.append(p)
    return dirs


def _setup_paths(entry_path):
    """插件目录 + 兄弟插件目录 + 项目根 + 宿主 src/stdlib + 编译器，全部入搜索路径。"""
    entry_dir = os.path.dirname(os.path.abspath(entry_path))
    paths = [entry_dir] + _plugin_search_dirs() + \
        [ROOT, PLUGINS, LH_SRC, LH_STDLIB, LIGHTHARNESS,
         os.path.join(LIGHT_MERGE, 'src'),
         os.path.join(LIGHT_MERGE, 'antlrparser'),
         LIGHT_MERGE]
    for p in paths:
        if os.path.isdir(p) and p not in sys.path:
            sys.path.insert(0, p)
    try:
        import _light_import_hook
        _light_import_hook.install([entry_dir] + _plugin_search_dirs() +
                                   [ROOT, PLUGINS, LH_SRC, LH_STDLIB])
    except Exception as exc:  # noqa: BLE001 - 钩子失败不致命，.py 版 stdlib 仍可用
        print('警告: 纯光明导入钩子安装失败: %s' % exc)


def main(argv=None):
    argv = list(sys.argv if argv is None else argv)
    if len(argv) < 2 or argv[1] in ('-h', '--help'):
        print(__doc__)
        return 0
    os.environ.setdefault('HARNESS_PY', sys.executable)
    os.environ.setdefault('HARNESS_ROOT', LIGHTHARNESS)
    entry = argv[1]
    if not os.path.isabs(entry):
        entry = os.path.join(ROOT, entry)
    if not os.path.isfile(entry):
        print('错误: 找不到入口文件 %s' % entry)
        return 1
    _setup_paths(entry)
    from cli.light import main as light_main
    sys.argv = ['light', 'run', entry] + argv[2:]
    return light_main()


if __name__ == '__main__':
    sys.exit(main())

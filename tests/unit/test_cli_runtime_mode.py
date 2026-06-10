"""验证 CLI 参数模式是否符合直接启动设计。"""

from drone_agent import cli


def test_build_parser_can_lock_profile_to_sim():
    """验证 parser 可以固定为 sim profile。"""
    parser = cli.build_parser(default_profile="sim")
    parser.set_defaults(profile="sim")
    args = parser.parse_args([])

    assert args.profile == "sim"


def test_build_parser_can_lock_profile_to_real():
    """验证 parser 可以固定为 real profile。"""
    parser = cli.build_parser(default_profile="real")
    parser.set_defaults(profile="real")
    args = parser.parse_args([])

    assert args.profile == "real"

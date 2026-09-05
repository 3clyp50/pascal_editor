import sys


def main() -> int:
    action = sys.argv[1] if len(sys.argv) > 1 else "status"
    from usr.plugins.pascal_editor.helpers import runtime

    config = runtime.get_config()
    print(f"Pascal Editor action: {action}")
    if action in {"stop", "shutdown"}:
        result = runtime.stop_runtime(config)
    elif action in {"restart", "reload"}:
        runtime.stop_runtime(config)
        result = runtime.ensure_running(config)
    elif action in {"start", "ensure", "open"}:
        result = runtime.ensure_running(config)
    else:
        result = runtime.get_status(config)
    print(result)
    return 0 if result.get("state") in {"running", "stopped", "disabled"} else 1


if __name__ == "__main__":
    sys.exit(main())

from pathlib import Path


def test_deploy_health_check_uses_docker_bridge_endpoint():
    script = (Path(__file__).parents[1] / "deploy" / "push.sh").read_text(encoding="utf-8")

    assert 'curl -sf 172.17.0.1:8010/health' in script
    assert 'curl -sf localhost:8010/health' not in script

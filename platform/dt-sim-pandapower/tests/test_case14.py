import pathlib
import sys


def _bootstrap_paths() -> None:
    repo_root = pathlib.Path(__file__).resolve().parents[3]  # .../pbl
    sys.path.insert(0, str(repo_root / "platform" / "dt-contracts" / "python" / "src"))
    sys.path.insert(0, str(repo_root / "platform" / "dt-sim-pandapower"))


_bootstrap_paths()


from dt_sim_pandapower.adapter import PandapowerAdapter  # noqa: E402


def test_ieee14_powerflow_converges_and_maps_results():
    adapter = PandapowerAdapter(grid_id="test-grid")
    net, snap = adapter.build_ieee14()
    run = adapter.run_powerflow(net)
    assert run.solved is True

    snap2 = adapter.apply_results_to_snapshot(snap, net)
    assert len(snap2.nodes) > 0
    assert any(("vm_pu" in n.dynamic) for n in snap2.nodes)


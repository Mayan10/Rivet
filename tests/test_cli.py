import json

import pytest

from rivet.cli import main


def test_generate_writes_files_and_returns_zero(tmp_path, capsys):
    out_dir = tmp_path / "out"
    exit_code = main(
        [
            "generate",
            "--width",
            "15",
            "--length",
            "13",
            "--road-width",
            "9",
            "--height",
            "6",
            "--room",
            "living_room",
            "--room",
            "master_bedroom+ensuite",
            "--room",
            "bedroom:2+ensuite",
            "--room",
            "kitchen",
            "--room",
            "dining_room",
            "--room",
            "bathroom",
            "--seed",
            "42",
            "--candidates",
            "2",
            "--out-dir",
            str(out_dir),
        ]
    )
    assert exit_code == 0
    assert (out_dir / "candidate-1.dxf").exists()
    assert (out_dir / "candidate-1.png").exists()
    assert (out_dir / "candidate-1.svg").exists()

    out = capsys.readouterr().out
    assert "score" in out


def test_generate_with_vastu_prints_preferences(tmp_path, capsys):
    out_dir = tmp_path / "out"
    exit_code = main(
        [
            "generate",
            "--width",
            "15",
            "--length",
            "13",
            "--road-width",
            "9",
            "--height",
            "6",
            "--room",
            "living_room",
            "--room",
            "master_bedroom+ensuite",
            "--room",
            "bedroom:2+ensuite",
            "--room",
            "kitchen",
            "--room",
            "dining_room",
            "--room",
            "bathroom",
            "--room",
            "pooja",
            "--vastu",
            "--plot-north",
            "north",
            "--seed",
            "42",
            "--candidates",
            "1",
            "--out-dir",
            str(out_dir),
            "--formats",
            "png",
        ]
    )
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "vastu:" in out
    assert "preferences satisfied" in out


def test_generate_vastu_without_plot_north_exits(tmp_path):
    with pytest.raises(SystemExit):
        main(
            [
                "generate",
                "--width",
                "15",
                "--length",
                "13",
                "--room",
                "living_room",
                "--vastu",
                "--seed",
                "1",
                "--out-dir",
                str(tmp_path / "out"),
            ]
        )


def test_generate_infeasible_request_returns_one(tmp_path, capsys):
    exit_code = main(
        [
            "generate",
            "--width",
            "5",
            "--length",
            "6",
            "--room",
            "living_room",
            "--room",
            "bedroom:2",
            "--room",
            "kitchen",
            "--room",
            "bathroom",
            "--seed",
            "1",
            "--out-dir",
            str(tmp_path / "out"),
        ]
    )
    assert exit_code == 1
    err = capsys.readouterr().err
    assert "INFEASIBLE" in err
    assert "TNCDBR 2019" in err  # cited violations reach the CLI output


def test_generate_rejects_unknown_room_type():
    with pytest.raises(SystemExit):
        main(["generate", "--width", "10", "--length", "10", "--room", "not_a_room"])


def test_rules_command_prints_valid_json(capsys):
    exit_code = main(["rules"])
    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert "bedroom" in payload
    assert payload["bedroom"]["citation"].startswith("TNCDBR 2019")


def test_rules_command_respects_ruleset_flag(capsys):
    main(["rules", "--ruleset", "generic"])
    payload = json.loads(capsys.readouterr().out)
    assert payload["bedroom"]["citation"] == "uncited placeholder"


def test_room_types_command_lists_known_types(capsys):
    exit_code = main(["room-types"])
    assert exit_code == 0
    out = capsys.readouterr().out.splitlines()
    assert "bedroom" in out
    assert "kitchen" in out

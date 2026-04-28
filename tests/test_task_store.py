"""Tests for task_manager — CRUD, atomic write, load/save/delete."""

from __future__ import annotations

from pathlib import Path

import pytest

from backend.models import Task, TaskStatus, TaskCreate, PlanStep, StepStatus
from backend.task_manager import (
    create_task,
    load_task,
    save_task,
    delete_task,
    list_tasks,
    add_progress_note,
    import_plan,
    update_step,
    complete_task,
    fail_task,
    generate_handoff_text,
)


class TestCreateTask:
    def test_creates_json_file(self, tasks_dir: Path, project_dir: Path):
        req = TaskCreate(
            task_id="my-task",
            name="my-task",
            project_dir=str(project_dir),
            command="echo hello",
        )
        task = create_task(req)
        assert task.task_id == "my-task"
        assert (tasks_dir / "my-task.json").exists()

    def test_rejects_invalid_task_id(self, project_dir: Path):
        req = TaskCreate(
            task_id="../evil",
            name="evil",
            project_dir=str(project_dir),
            command="echo",
        )
        with pytest.raises(ValueError, match="Invalid task_id"):
            create_task(req)

    def test_rejects_unsafe_project_dir(self):
        req = TaskCreate(
            task_id="safe-id",
            name="safe",
            project_dir="/etc",
            command="echo",
        )
        with pytest.raises(ValueError, match="Unsafe project_dir"):
            create_task(req)


class TestLoadTask:
    def test_loads_existing_task(self, sample_task_json: Path, sample_task: Task):
        loaded = load_task(sample_task.task_id)
        assert loaded is not None
        assert loaded.task_id == sample_task.task_id
        assert loaded.command == sample_task.command

    def test_returns_none_for_missing(self):
        assert load_task("nonexistent") is None

    def test_returns_none_for_invalid_id(self):
        assert load_task("../../etc") is None


class TestSaveTask:
    def test_atomic_write(self, tasks_dir: Path, project_dir: Path):
        req = TaskCreate(
            task_id="atomic-test",
            name="atomic-test",
            project_dir=str(project_dir),
            command="echo",
        )
        task = create_task(req)
        task.goal = "Updated goal"
        save_task(task)

        loaded = load_task("atomic-test")
        assert loaded is not None
        assert loaded.goal == "Updated goal"

    def test_no_temp_files_left(self, tasks_dir: Path, project_dir: Path):
        req = TaskCreate(
            task_id="clean-test",
            name="clean-test",
            project_dir=str(project_dir),
            command="echo",
        )
        create_task(req)
        tmp_files = list(tasks_dir.glob("*.tmp"))
        assert len(tmp_files) == 0


class TestDeleteTask:
    def test_deletes_existing(self, sample_task_json: Path, sample_task: Task):
        assert delete_task(sample_task.task_id) is True
        assert not sample_task_json.exists()

    def test_returns_false_for_missing(self):
        assert delete_task("nonexistent") is False


class TestListTasks:
    def test_lists_all_tasks(self, tasks_dir: Path, project_dir: Path):
        for name in ("task-a", "task-b", "task-c"):
            req = TaskCreate(
                task_id=name,
                name=name,
                project_dir=str(project_dir),
                command="echo",
            )
            create_task(req)

        tasks = list_tasks()
        assert len(tasks) == 3
        ids = {t.task_id for t in tasks}
        assert ids == {"task-a", "task-b", "task-c"}

    def test_empty_dir(self):
        tasks = list_tasks()
        assert tasks == []


class TestProgressNotes:
    def test_add_note(self, sample_task_json: Path, sample_task: Task):
        task = add_progress_note(sample_task.task_id, "Did something")
        assert task is not None
        assert len(task.progress_log) == 1
        assert task.progress_log[0].message == "Did something"

    def test_returns_none_for_missing(self):
        assert add_progress_note("nonexistent", "note") is None


class TestPlanManagement:
    def test_import_plan(self, sample_task_json: Path, sample_task: Task):
        steps = [
            PlanStep(id="1", title="Step one"),
            PlanStep(id="2", title="Step two"),
        ]
        task = import_plan(sample_task.task_id, steps)
        assert task is not None
        assert len(task.plan) == 2
        assert task.current_step_id == "1"

    def test_update_step(self, sample_task_json: Path, sample_task: Task):
        steps = [PlanStep(id="1", title="Step one")]
        import_plan(sample_task.task_id, steps)

        task = update_step(sample_task.task_id, "1", StepStatus.done, "Done!")
        assert task is not None
        assert task.plan[0].status == StepStatus.done
        assert task.plan[0].notes == "Done!"


class TestCompleteFail:
    def test_complete_task(self, sample_task_json: Path, sample_task: Task):
        task = complete_task(sample_task.task_id, "All done")
        assert task is not None
        assert task.status == TaskStatus.completed
        assert task.final_summary == "All done"
        assert task.ended_at is not None

    def test_fail_task(self, sample_task_json: Path, sample_task: Task):
        task = fail_task(sample_task.task_id, "Crashed")
        assert task is not None
        assert task.status == TaskStatus.failed
        assert task.risk_notes == "Crashed"


class TestHandoff:
    def test_generate_handoff(self, sample_task_json: Path, sample_task: Task):
        text = generate_handoff_text(sample_task.task_id)
        assert text is not None
        assert "test-task-1" in text
        assert "Train the model" in text

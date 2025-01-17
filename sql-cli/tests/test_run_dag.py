import pathlib
from unittest import mock

from airflow.decorators import task
from airflow.utils.cli import get_dag
from airflow.utils.trigger_rule import TriggerRule

from astro import sql as aql
from sql_cli.run_dag import _run_task, run_dag

CWD = pathlib.Path(__file__).parent


@mock.patch("airflow.models.taskinstance.TaskInstance")
@mock.patch("airflow.settings.SASession")
def test_run_task_successfully(mock_session, mock_task_instance):
    mock_task_instance.map_index = 0
    _run_task(mock_task_instance, mock_session)
    mock_task_instance._run_raw_task.assert_called_once()
    mock_session.flush.assert_called_once()


def test_run_task_cleanup_log(sample_dag, capsys):
    @aql.dataframe
    def upstream_task():
        return 5

    @aql.dataframe
    def downstream_task(f):
        return f

    with sample_dag:
        downstream_task(upstream_task())
        aql.cleanup()
    run_dag(sample_dag)
    captured = capsys.readouterr()
    assert "aql.cleanup async, continuing" in captured.out


def test_run_dag_dynamic_task(sample_dag, capsys):
    @task
    def get_list():
        return [1, 2, 3]

    @task
    def print_val(v):
        print(v)

    with sample_dag:
        print_val.expand(v=get_list())
    run_dag(sample_dag)
    captured = capsys.readouterr()
    for i in [1, 2]:
        assert f"Running task %s index %d print_val {i}" in captured.out


def test_run_dag_with_skip(sample_dag, capsys):
    @task.branch
    def who_is_prettiest():
        return "snow_white_wins"

    @task
    def snow_white_wins():
        return "the witch is mad"

    @task
    def witch_wins():
        return "the witch is happy"

    @task(trigger_rule=TriggerRule.NONE_FAILED_MIN_ONE_SUCCESS)
    def movie_ends():
        return "movie ends"

    with sample_dag:
        who_is_prettiest() >> [snow_white_wins(), witch_wins()] >> movie_ends()  # skipcq: PYL-W0106
    run_dag(sample_dag)
    captured = capsys.readouterr()
    assert "witch_wins ran successfully!" not in captured.out
    assert "snow_white_wins ran successfully!" in captured.out
    assert "movie_ends ran successfully!" in captured.out


def test_run_dag(capsys):
    dag = get_dag(dag_id="example_dataframe", subdir=f"{CWD}/test_dag")
    run_dag(dag)
    captured = capsys.readouterr()
    assert "The worst month was" in captured.out


def test_run_dag_with_conn_id(capsys):
    dag = get_dag(dag_id="example_sqlite_load_transform", subdir=f"{CWD}/test_dag")
    run_dag(dag, conn_file_path=f"{CWD}/test_conn.yaml")
    captured = capsys.readouterr()
    assert "top movie:" in captured.out

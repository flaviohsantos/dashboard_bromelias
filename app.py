KeyError: This app has encountered an error. The original error message is redacted to prevent data leaks. Full error details have been recorded in the logs (if you're on Streamlit Cloud, click on 'Manage app' in the lower right of your app).
Traceback:
File "/home/adminuser/venv/lib/python3.11/site-packages/streamlit/runtime/scriptrunner/exec_code.py", line 88, in exec_func_with_error_handling
    result = func()
             ^^^^^^
File "/home/adminuser/venv/lib/python3.11/site-packages/streamlit/runtime/scriptrunner/script_runner.py", line 590, in code_to_exec
    exec(code, module.__dict__)
File "/mount/src/dashboard_bromelias/app.py", line 46, in <module>
    "id_bromelia": df_campo["id_bromelia_calc"],
                   ~~~~~~~~^^^^^^^^^^^^^^^^^^^^
File "/home/adminuser/venv/lib/python3.11/site-packages/pandas/core/frame.py", line 4102, in __getitem__
    indexer = self.columns.get_loc(key)
              ^^^^^^^^^^^^^^^^^^^^^^^^^
File "/home/adminuser/venv/lib/python3.11/site-packages/pandas/core/indexes/base.py", line 3812, in get_loc
    raise KeyError(key) from err

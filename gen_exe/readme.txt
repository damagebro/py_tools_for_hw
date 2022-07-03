ex. pyinstaller -D -F -n hello hello.py
ex. pyinstaller -D -F -p <import_path> -n hello hello.py
ex. pyinstaller -D -F -p ..\autogen_reg\src\ -n autogen_reg.exe ..\autogen_reg\src\autogen_reg.py

-p DIR, --paths DIR   A path to search for imports (like using PYTHONPATH).
                        Multiple paths are allowed, separated by ';', or use
                        this option multiple times
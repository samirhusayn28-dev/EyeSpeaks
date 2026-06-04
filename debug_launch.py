"""
EyeSpeaks Debug Launcher
Run this instead of main.py to see all errors
"""
import sys
import traceback

try:
    print("Step 1: Importing Qt...")
    from PyQt5.QtWidgets import QApplication
    print("Step 2: Qt OK")

    print("Step 3: Importing main window...")
    from main import MainWindow
    print("Step 4: MainWindow imported OK")

    print("Step 5: Creating app...")
    app = QApplication(sys.argv)
    print("Step 6: App created OK")

    print("Step 7: Creating window...")
    win = MainWindow()
    print("Step 8: Window created OK — app should be visible now")

    print("Step 9: Running event loop...")
    code = app.exec_()
    print(f"Step 10: App exited with code {code}")
    sys.exit(code)

except Exception as e:
    print("\n========== CRASH ==========")
    traceback.print_exc()
    print("===========================")
    input("\nPress ENTER to exit...")
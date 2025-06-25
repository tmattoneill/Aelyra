# Check if main.py is trying to import something that doesn't exist
python -c "
import sys
print('Python executable:', sys.executable)
print('Python path:', sys.path[:3])
try:
    import fastapi
    print('FastAPI import: SUCCESS')
    print('FastAPI location:', fastapi.__file__)
except Exception as e:
    print('FastAPI import ERROR:', e)
"
import sys
sys.path.insert(0, r"C:\Users\Dawis\ForeverRouteJarvis")
from DevinBridge import jarvis_tools
sys.argv = ["jarvis_tools"] + sys.argv[1:]
sys.exit(jarvis_tools.main())

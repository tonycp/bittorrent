from tkinter import Frame as _Frame
from typing import List as _List

from filter_panel import FilterPanel
from source_panel import SourcePanel
from nav_bar import NavBar

widgets: _List[type[_Frame]] = [
    FilterPanel,
    SourcePanel,
    NavBar,
]

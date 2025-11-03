# WASD Viewport Controls
It's an attempt to implement a convenient Godot/Unreal viewport manipulation with WASD(QE) keys.

<img width="208" height="96" alt="image" src="https://github.com/user-attachments/assets/1f0a79fd-21d4-4f25-9385-cc0e2f98fa2b" />

## Installation
Download or clone the repository into your documents/maya/scripts folder.
It should work for Maya 2022+.

## How to use
Run the script inside Maya with the following command.
```python
from wasd_viewport_controls import controlPanel
controlPanel.show()
```
Then press `ENABLE` button and enjoy.

⚠️ As Maya uses a mouse right button for context menus, the script uses Alt modificator for the keys.

The tool supports WASD and QE keys as well as F for framing selected objects. 

## Tips
Don't forget to press Alt with those keys!

Remove hotkeys on Alt + WASDQEF keys in order to avoid clashes if you have any.

In case of bugs, let me know or open an issue here.

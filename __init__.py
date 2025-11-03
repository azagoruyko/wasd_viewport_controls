try:
    from shiboken2 import wrapInstance
    from PySide2 import QtWidgets, QtCore
except ImportError: # Maya 2024 and newer
    from shiboken6 import wrapInstance
    from PySide6 import QtWidgets, QtCore

import maya.OpenMayaUI as omui
import maya.api.OpenMaya as om
import maya.cmds as cmds

mayaMainWindow = wrapInstance(int(omui.MQtUtil.mainWindow()), QtWidgets.QWidget)

def clamp(value, min_value, max_value):
    return max(min_value, min(max_value, value))

class CameraControlFilter(QtCore.QObject):
    # Precomputed mapping from key to local direction vector
    KEY_VECTORS = {
        QtCore.Qt.Key_A: om.MVector(-1, 0, 0),  # left
        QtCore.Qt.Key_D: om.MVector(1, 0, 0),   # right
        QtCore.Qt.Key_W: om.MVector(0, 0, -1),  # forward
        QtCore.Qt.Key_S: om.MVector(0, 0, 1),   # backward
        QtCore.Qt.Key_E: om.MVector(0, 1, 0),   # up
        QtCore.Qt.Key_Q: om.MVector(0, -1, 0),  # down
    }

    MOVE_SCALE_FACTOR = 0.1
    DEFAULT_TIMER_MS = 5 # lower - smoother, slower a bit

    def __init__(self, moveStep=0.1):
        super().__init__()

        self.moveStep = moveStep
        
        self._movingKeys = set()
        self._altPressed = False

        # Single repeating timer to drive camera movement at a fixed rate
        self.moveTimer = QtCore.QTimer(self)
        self.moveTimer.setInterval(self.DEFAULT_TIMER_MS) 
        self.moveTimer.timeout.connect(self.moveCameraLoop)

    def _startMovementTimer(self):
        if not self._movingKeys and not self.moveTimer.isActive():
            self.moveTimer.start()

    def _stopMovementTimer(self):
        if self.moveTimer.isActive():
            self.moveTimer.stop()

    def eventFilter(self, obj, event):
        if event.type() == QtCore.QEvent.KeyPress:
            key = event.key()

            if key == QtCore.Qt.Key_Alt:
                self._altPressed = True

            elif self._altPressed and key == QtCore.Qt.Key_F: # frame selected
                cmds.LookAtSelection()
                cmds.FrameSelected()

            # Ignore auto-repeated key press events to prevent multiple timer triggers
            elif self._altPressed and key in self.KEY_VECTORS and not event.isAutoRepeat():
                # Start the timer only once when the first movement key is pressed
                self._startMovementTimer()
                self._movingKeys.add(key)

        elif event.type() == QtCore.QEvent.KeyRelease:
            key = event.key()
            if key == QtCore.Qt.Key_Alt:
                self._altPressed = False
                self._movingKeys.clear()

            # Ignore auto-repeated key release events
            if not event.isAutoRepeat():
                if key in self._movingKeys:
                    self._movingKeys.remove(key)
                    
            # Stop the timer when no movement keys are held or Alt is released
            if not self._altPressed or not self._movingKeys:
                self._stopMovementTimer()

        return False

    def moveCameraLoop(self):
        if not self._altPressed or not self._movingKeys:
            return

        moveVector = om.MVector()
        for key in self._movingKeys:
            moveVector += self.KEY_VECTORS.get(key, om.MVector(0, 0, 0))

        if moveVector.length() > 0:
            moveVector = moveVector.normal()
            
            # Constant distance per tick ensures linear motion over time
            self.moveCameraLocal(moveVector, distance=self.moveStep)

    def moveCameraLocal(self, localDir, distance):
        panel = cmds.getPanel(withFocus=True)

        # Only operate when the focused panel is a viewport (modelPanel)
        if not panel or cmds.getPanel(typeOf=panel) != 'modelPanel':
            return

        cam = cmds.modelEditor(panel, query=True, camera=True)
        camPos = om.MVector(cmds.xform(cam, q=True, ws=True, t=True))
        coiPos = om.MVector(cmds.camera(cam, q=True, worldCenterOfInterest=True))
        camMat = om.MMatrix(cmds.getAttr(cam + ".worldMatrix"))

        # Scale movement purely by camera attributes: distance from camera to its world COI
        scaleMetric = (coiPos - camPos).length()
        
        scaledDistance = distance * scaleMetric * self.MOVE_SCALE_FACTOR

        worldDir = (localDir * camMat).normal()
        newCamPos = camPos + worldDir * scaledDistance

        cmds.xform(cam, ws=True, t=(newCamPos.x, newCamPos.y, newCamPos.z))
        cmds.refresh()
    

class ViewportControlPanel(QtWidgets.QFrame):
    STEP_MIN = 0.01
    STEP_MAX = 0.20

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        
        # Own the filter inside the panel
        self.cameraFilter = CameraControlFilter()
        self.isInstalled = False

        # Window settings
        self.setWindowTitle("WASD Viewport Controls")
        self.setWindowFlags(QtCore.Qt.Tool)

        layout = QtWidgets.QVBoxLayout(self)

        # Enabled toggle button (checked = active)
        self.enabledButton = QtWidgets.QPushButton("ENABLE")
        self.enabledButton.setCheckable(True)
        self.enabledButton.toggled.connect(self.onEnabledToggled)

        # Move step slider
        stepLayout = QtWidgets.QHBoxLayout()
        self.stepSlider = QtWidgets.QSlider(QtCore.Qt.Horizontal)

        # Integer range maps to STEP_MIN..STEP_MAX via x/100
        self.stepSlider.setRange(int(self.STEP_MIN * 100), int(self.STEP_MAX * 100))
        self.stepSlider.setSingleStep(1)
        self.stepSlider.valueChanged.connect(self.onStepSliderChanged)

        self.stepValueLabel = QtWidgets.QLabel("")
        stepLayout.addWidget(QtWidgets.QLabel("Move step:"))
        stepLayout.addWidget(self.stepSlider)
        stepLayout.addWidget(self.stepValueLabel)

        # Layout
        layout.addWidget(self.enabledButton)
        layout.addLayout(stepLayout)

        # Initialize from current filter if any
        self.refreshFromFilter()

    def refreshFromFilter(self):
        # Enabled state reflects whether filter is installed
        self.enabledButton.setChecked(self.isInstalled)

        # Step
        step = float(self.cameraFilter.moveStep)
        stepInt = clamp(int(round(step * 100)), int(self.STEP_MIN * 100), int(self.STEP_MAX * 100))
        self.stepSlider.setValue(stepInt)
        self.stepValueLabel.setText(f"{step:.3f}")

    def installCameraControls(self):
        mayaMainWindow.installEventFilter(self.cameraFilter)
        self.isInstalled = True

        cmds.headsUpDisplay('wasd_viewport_controls', section=5, block=1, labelFontSize='large',
                            label='WASD Viewport Controls\tUse Alt + WASDQE, Alt+F - frame selected')

    def uninstallCameraControls(self):
        mayaMainWindow.removeEventFilter(self.cameraFilter)
        self.isInstalled = False

        if cmds.headsUpDisplay('wasd_viewport_controls', exists=True):
            cmds.headsUpDisplay('wasd_viewport_controls', remove=True)

    def onEnabledToggled(self, checked):
        if checked and not self.isInstalled:
            self.installCameraControls()

        elif not checked and self.isInstalled:
            self.uninstallCameraControls()

        self.enabledButton.setText("DISABLE" if self.isInstalled else "ENABLE")

    def onStepSliderChanged(self, val):
        step = clamp(float(val) / 100.0, self.STEP_MIN, self.STEP_MAX)
        self.stepValueLabel.setText(f"{step:.3f}")
        self.cameraFilter.moveStep = step

# Initialize panel; it owns its filter instance
controlPanel = ViewportControlPanel(parent=mayaMainWindow)
#controlPanel.show()

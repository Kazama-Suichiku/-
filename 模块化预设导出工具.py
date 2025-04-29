import maya.cmds as cmds
import maya.OpenMayaUI as omui
from PySide6 import QtWidgets, QtCore, QtGui
import shiboken6
import os
import json

# 配置文件路径，保存角落设置
CONFIG_FILE = os.path.expanduser("~/.maya_pivot_adjust_config.json")

def set_pivot_to_bounding_box_corner(use_max_dict):
    """将选中物体的枢轴点移到边界框指定角落"""
    selected_objs = cmds.ls(selection=True)
    if not selected_objs:
        cmds.warning("请先选择物体！")
        return
    for obj in selected_objs:
        try:
            bounding_box = cmds.xform(obj, q=True, boundingBox=True, ws=True)
            new_pivot = []
            for axis in ['X', 'Y', 'Z']:
                min_idx = {'X': 0, 'Y': 1, 'Z': 2}[axis]
                max_idx = min_idx + 3
                new_pivot.append(bounding_box[max_idx] if use_max_dict[axis] else bounding_box[min_idx])
            cmds.xform(obj, rp=new_pivot, sp=new_pivot, ws=True)
            print(f"{obj} 枢轴点已移至 {new_pivot}")
        except Exception as e:
            print(f"处理 {obj} 失败：{e}")

def move_object_to_world_origin():
    """将选中物体的枢轴点移到世界原点 [0, 0, 0]，保持角落位置"""
    selected_objs = cmds.ls(selection=True)
    if not selected_objs:
        cmds.warning("请先选择物体！")
        return
    for obj in selected_objs:
        try:
            current_pivot = cmds.xform(obj, q=True, rp=True, ws=True)
            move_vector = [-current_pivot[0], -current_pivot[1], -current_pivot[2]]
            cmds.xform(obj, t=move_vector, ws=True, r=True)
            print(f"{obj} 已移至世界原点")
        except Exception as e:
            print(f"处理 {obj} 失败：{e}")

def freeze_transformations():
    """冻结选中物体的变换，重置为默认值"""
    selected_objs = cmds.ls(selection=True)
    if not selected_objs:
        cmds.warning("请先选择物体！")
        return
    for obj in selected_objs:
        try:
            if not cmds.objectType(obj, isType="mesh") and not cmds.listRelatives(obj, shapes=True, type="mesh"):
                continue
            cmds.makeIdentity(obj, apply=True, translate=True, rotate=True, scale=True, normal=False)
            print(f"{obj} 变换已冻结")
        except Exception as e:
            print(f"冻结 {obj} 失败：{e}")

def export_fbx_to_path(freeze_before_export=True, scale_factor=1.0):
    """将选中物体单独导出为FBX文件，以厘米为单位"""
    selected_objs = cmds.ls(selection=True)
    if not selected_objs:
        cmds.warning("请先选择物体！")
        return

    if not cmds.pluginInfo("fbxmaya", q=True, loaded=True):
        try:
            cmds.loadPlugin("fbxmaya")
        except Exception as e:
            cmds.error(f"加载FBX插件失败：{e}")
            return

    export_path = QtWidgets.QFileDialog.getExistingDirectory(None, "选择导出路径", os.path.expanduser("~"))
    if not export_path:
        cmds.warning("未选择导出路径！")
        return
    if not os.access(export_path, os.W_OK):
        cmds.warning(f"路径 {export_path} 不可写！")
        return

    original_selection = cmds.ls(selection=True)
    for obj in selected_objs:
        try:
            if not cmds.objectType(obj, isType="mesh") and not cmds.listRelatives(obj, shapes=True, type="mesh"):
                continue
            cmds.select(obj, r=True)
            if scale_factor != 1.0:
                cmds.scale(scale_factor, scale_factor, scale_factor, obj, relative=True)
            if freeze_before_export:
                cmds.makeIdentity(obj, apply=True, translate=True, rotate=True, scale=True, normal=False)
            safe_obj_name = obj.replace(":", "_").replace("|", "_")
            fbx_file = os.path.join(export_path, f"{safe_obj_name}.fbx")
            cmds.FBXResetExport()
            try:
                cmds.FBXExportConvertUnitString("-v", "cm")
            except AttributeError:
                print("警告：需手动设置FBX单位为厘米")
            cmds.FBXExport("-f", fbx_file, "-s")
            print(f"{obj} 已导出为 {fbx_file}")
        except Exception as e:
            print(f"导出 {obj} 失败：{e}")
        finally:
            cmds.select(original_selection, r=True)

class PivotAdjustUI(QtWidgets.QDialog):
    """模块化预设导出工具UI"""
    def __init__(self):
        super(PivotAdjustUI, self).__init__()
        self.setWindowTitle("模块化预设导出工具")
        self.setFixedSize(400, 320)
        self.create_ui()
        self.load_config()

    def create_ui(self):
        layout = QtWidgets.QVBoxLayout()
        layout.setSpacing(10)
        layout.setContentsMargins(15, 15, 15, 15)

        font = QtGui.QFont()
        font.setPointSize(10)

        # 轴选择
        axis_group = QtWidgets.QGroupBox("选择轴最小/最大值")
        axis_group.setFont(font)
        axis_layout = QtWidgets.QFormLayout()
        self.axis_combos = {}
        for axis in ['X', 'Y', 'Z']:
            combo = QtWidgets.QComboBox()
            combo.addItems(['Min', 'Max'])
            combo.setFont(font)
            self.axis_combos[axis] = combo
            axis_layout.addRow(f"{axis} 轴:", combo)
        axis_group.setLayout(axis_layout)
        layout.addWidget(axis_group)

        # 按钮
        apply_pivot_btn = QtWidgets.QPushButton("应用枢轴点到边界框角落")
        apply_pivot_btn.setFont(font)
        apply_pivot_btn.setFixedHeight(30)
        apply_pivot_btn.clicked.connect(self.apply_pivot_to_corner)
        layout.addWidget(apply_pivot_btn)

        move_object_btn = QtWidgets.QPushButton("移动枢轴点到世界原点")
        move_object_btn.setFont(font)
        move_object_btn.setFixedHeight(30)
        move_object_btn.clicked.connect(self.move_object_to_world_origin)
        layout.addWidget(move_object_btn)

        freeze_transform_btn = QtWidgets.QPushButton("冻结变换")
        freeze_transform_btn.setFont(font)
        freeze_transform_btn.setFixedHeight(30)
        freeze_transform_btn.clicked.connect(self.freeze_transformations)
        layout.addWidget(freeze_transform_btn)

        export_fbx_btn = QtWidgets.QPushButton("一键导出FBX")
        export_fbx_btn.setFont(font)
        export_fbx_btn.setFixedHeight(30)
        export_fbx_btn.clicked.connect(self.export_fbx_to_path)
        layout.addWidget(export_fbx_btn)

        cancel_btn = QtWidgets.QPushButton("取消")
        cancel_btn.setFont(font)
        cancel_btn.setFixedHeight(30)
        cancel_btn.clicked.connect(self.close)
        layout.addWidget(cancel_btn)

        layout.addStretch()
        self.setLayout(layout)

    def apply_pivot_to_corner(self):
        use_max_dict = {axis: combo.currentText() == 'Max' for axis, combo in self.axis_combos.items()}
        set_pivot_to_bounding_box_corner(use_max_dict)
        self.save_config(use_max_dict)

    def move_object_to_world_origin(self):
        move_object_to_world_origin()

    def freeze_transformations(self):
        freeze_transformations()

    def export_fbx_to_path(self):
        export_fbx_to_path(freeze_before_export=True, scale_factor=1.0)

    def save_config(self, use_max_dict):
        """保存角落设置到配置文件"""
        try:
            with open(CONFIG_FILE, 'w') as f:
                json.dump(use_max_dict, f)
        except Exception as e:
            print(f"保存配置失败：{e}")

    def load_config(self):
        """加载角落设置"""
        try:
            if os.path.exists(CONFIG_FILE):
                with open(CONFIG_FILE, 'r') as f:
                    config = json.load(f)
                for axis, is_max in config.items():
                    self.axis_combos[axis].setCurrentText('Max' if is_max else 'Min')
        except Exception as e:
            print(f"加载配置失败：{e}")

def get_maya_main_window():
    """获取Maya主窗口"""
    main_window_ptr = omui.MQtUtil.mainWindow()
    if main_window_ptr:
        return shiboken6.wrapInstance(int(main_window_ptr), QtWidgets.QWidget)
    return None

def show_ui():
    """显示UI窗口"""
    parent = get_maya_main_window()
    if not parent:
        cmds.error("无法找到Maya主窗口！")
        return
    for widget in QtWidgets.QApplication.allWidgets():
        if isinstance(widget, PivotAdjustUI):
            widget.close()
    ui = PivotAdjustUI()
    ui.setParent(parent, QtCore.Qt.Window)
    ui.show()

if __name__ == "__main__":
    show_ui()
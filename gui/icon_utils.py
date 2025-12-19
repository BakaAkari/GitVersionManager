from PyQt5.QtGui import QIcon, QPixmap, QPainter, QColor, QBrush, QPen, QPolygonF
from PyQt5.QtCore import Qt, QSize, QPointF

class IconUtils:
    @staticmethod
    def create_circle_icon(color: str, size: int = 16) -> QIcon:
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Draw circle
        painter.setBrush(QBrush(QColor(color)))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(2, 2, size-4, size-4)
        
        painter.end()
        return QIcon(pixmap)
    
    @staticmethod
    def create_arrow_icon(color: str, direction: str = "up", size: int = 16) -> QIcon:
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        
        painter.setBrush(QBrush(QColor(color)))
        painter.setPen(Qt.NoPen)
        
        # Draw arrow
        if direction == "up":
            points = [QPointF(size/2, 2), QPointF(size-3, size-3), QPointF(3, size-3)]
        else: # down
            points = [QPointF(3, 3), QPointF(size-3, 3), QPointF(size/2, size-2)]
            
        painter.drawPolygon(QPolygonF(points))
        
        painter.end()
        return QIcon(pixmap)

    @staticmethod
    def create_menu_icon(color: str = "#d0d0d0", size: int = 16) -> QIcon:
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        
        pen = QPen(QColor(color))
        pen.setWidth(2)
        painter.setPen(pen)
        
        # Draw 3 lines
        margin = 3
        painter.drawLine(margin, 4, size-margin, 4)
        painter.drawLine(margin, int(size/2), size-margin, int(size/2))
        painter.drawLine(margin, size-4, size-margin, size-4)
        
        painter.end()
        return QIcon(pixmap)

    @staticmethod
    def get_status_icon(status: str) -> QIcon:
        if status == "synced":
            return IconUtils.create_circle_icon("#4CAF50") # Green
        elif status == "modified":
            return IconUtils.create_circle_icon("#FFC107") # Amber
        elif status == "ahead":
            return IconUtils.create_arrow_icon("#2196F3", "up") # Blue
        elif status == "behind":
            return IconUtils.create_arrow_icon("#E91E63", "down") # Pink
        elif status == "conflict":
            return IconUtils.create_circle_icon("#F44336") # Red
        elif status == "checking":
            return IconUtils.create_circle_icon("#9E9E9E") # Grey
        elif status == "not_git":
            return IconUtils.create_circle_icon("#607D8B") # Blue Grey
        else:
            return IconUtils.create_circle_icon("#757575") # Dark Grey

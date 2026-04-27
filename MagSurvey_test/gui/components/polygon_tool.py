import numpy as np
import pandas as pd
from pathlib import Path
from tkinter import simpledialog, messagebox

class PolygonTool:
    def __init__(self, ax, canvas, survey_data, output_dir, main_window=None, on_deactivate=None):
        self.ax = ax
        self.canvas = canvas
        self.survey_data = survey_data
        self.output_dir = output_dir
        self.active = False
        self.points = []
        self.lines = []
        self.polygon_closed = False
        self.scatter_first = None
        self.on_deactivate = on_deactivate
        self._cid_click = None
        self._cid_key = None
        self.main_window = main_window

    def activate(self):
        if self.active:
            return
        self.active = True
        self._clear_temp()
        self._cid_click = self.canvas.mpl_connect('button_press_event', self._on_click)
        self._cid_dblclick = self.canvas.mpl_connect('button_press_event', self._on_dblclick)
        self._cid_key = self.canvas.mpl_connect('key_press_event', self._on_key)

    def deactivate(self):
        if not self.active:
            return
        self.active = False
        if self._cid_click:
            self.canvas.mpl_disconnect(self._cid_click)
        if self._cid_key:
            self.canvas.mpl_disconnect(self._cid_key)
        if hasattr(self, '_cid_dblclick'):
            self.canvas.mpl_disconnect(self._cid_dblclick)
        self._clear_temp()
        if self.on_deactivate:
            self.on_deactivate()

    def _clear_temp(self):
        for line in self.lines:
            line.remove()
        self.lines.clear()
        if self.scatter_first:
            self.scatter_first.remove()
            self.scatter_first = None
        self.points = []
        self.polygon_closed = False
        self.canvas.draw_idle()

    def _on_key(self, event):
        if event.key == 'enter':
            if not self.polygon_closed:
                messagebox.showinfo("Инфо", "Сначала замкните полигон.")
                return
            self._save_polygon()

    def _on_dblclick(self, event):
        if event.dblclick and event.inaxes == self.ax and event.button == 1:
            x, y = event.xdata, event.ydata
            if x is not None and y is not None:
                # Если уже замкнут, игнорируем
                if self.polygon_closed:
                    return
                new_point = (x, y)
                self.points.append(new_point)
                # Замыкаем на первую точку
                self.polygon_closed = True
                self.points.append(self.points[0])
                self._redraw()
                self._save_polygon()

    def _save_polygon(self):
        name = simpledialog.askstring("Имя полигона", "Введите название:",
                                    parent=self.ax.figure.canvas.get_tk_widget().winfo_toplevel())
        if not name:
            return

        out_dir = Path(self.output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        filepath = out_dir / f"{name}.xlsx"

        if filepath.exists():
            overwrite = messagebox.askyesno(
                "Файл существует",
                f"Файл '{name}.xlsx' уже существует.\nПерезаписать его?",
                parent=self.ax.figure.canvas.get_tk_widget().winfo_toplevel()
            )
            if not overwrite:
                new_name = simpledialog.askstring("Новое имя",
                                                "Введите другое имя:",
                                                parent=self.ax.figure.canvas.get_tk_widget().winfo_toplevel())
                if not new_name:
                    return
                name = new_name
                filepath = out_dir / f"{name}.xlsx"

        polygon_vertices = self.points[:-1]
        filtered = {}
        for sheet, df in self.survey_data.items():
            if 'lon' not in df.columns or 'lat' not in df.columns:
                continue
            mask = df.apply(lambda r: self._point_in_polygon((r['lon'], r['lat']), polygon_vertices), axis=1)
            fdf = df[mask]
            if not fdf.empty:
                filtered[sheet] = fdf

        if not filtered:
            messagebox.showinfo("Результат", "В полигон не попало ни одной точки.")
            return

        with pd.ExcelWriter(filepath) as writer:
            for sheet, fdf in filtered.items():
                fdf.to_excel(writer, sheet_name=sheet, index=False)

        if self.main_window:
            total_points = sum(len(fdf) for fdf in filtered.values())
            stats_msg = (f"Создан полигон '{name}' в папке {out_dir}\n"
                        f"Вершин: {len(polygon_vertices)}, точек внутри: {total_points}")
            self.main_window.master.after(0, lambda: self.main_window._add_statistics(stats_msg))

        messagebox.showinfo("Успех", f"Сохранено: {filepath}\nЛистов: {len(filtered)}")

        # Закрываем окно карты
        self.deactivate()
        win = self.ax.figure.canvas.get_tk_widget().winfo_toplevel()
        win.destroy()

    def _redraw(self):
        for line in self.lines:
            line.remove()
        self.lines.clear()
        if self.scatter_first:
            self.scatter_first.remove()
            self.scatter_first = None

        if len(self.points) < 2:
            self.canvas.draw_idle()
            return

        pts = np.array(self.points)
        for i in range(len(pts)-1):
            line, = self.ax.plot(pts[i:i+2, 0], pts[i:i+2, 1],
                                 '-o', markersize=8, linewidth=3, color='yellow',
                                 markeredgecolor='black', markeredgewidth=1,
                                 zorder=10)
            self.lines.append(line)

        if self.polygon_closed:
            line, = self.ax.plot([pts[-1,0], pts[0,0]], [pts[-1,1], pts[0,1]],
                                 '-', linewidth=3, color='yellow', zorder=10)
            self.lines.append(line)
            self.scatter_first = self.ax.scatter(*pts[0], color='red', s=120, zorder=11)

        self.canvas.draw_idle()

    @staticmethod
    def _distance(p1, p2):
        return np.sqrt((p1[0]-p2[0])**2 + (p1[1]-p2[1])**2)

    def _adaptive_threshold(self):
        """Возвращает порог замыкания как 0.25% от среднего диапазона по осям."""
        xlim = self.ax.get_xlim()
        ylim = self.ax.get_ylim()
        dx = xlim[1] - xlim[0]
        dy = ylim[1] - ylim[0]
        return 0.025 * max(dx, dy)  # можно настроить множитель

    def _on_click(self, event):
        if event.inaxes != self.ax or event.button != 1:
            return
        x, y = event.xdata, event.ydata
        if x is None or y is None:
            return
        new_point = (x, y)

        close_thresh = self._adaptive_threshold()

        if len(self.points) >= 3 and not self.polygon_closed:
            if self._distance(new_point, self.points[0]) < close_thresh:
                self.polygon_closed = True
                self.points.append(self.points[0])  # замыкающая вершина
                self._redraw()
                self._save_polygon()
                return

        if self.polygon_closed:
            self._clear_temp()
            self.points.append(new_point)
            self._redraw()
            return

        self.points.append(new_point)
        if len(self.points) == 1:
            pt, = self.ax.plot(x, y, 'o', markersize=8, color='yellow',
                               markeredgecolor='black', markeredgewidth=1, zorder=10)
            self.lines.append(pt)
            self.canvas.draw_idle()   # ← мгновенное отображение первой точки
        else:
            self._redraw()

    @staticmethod
    def _point_in_polygon(point, polygon):
        x, y = point
        n = len(polygon)
        inside = False
        j = n - 1
        for i in range(n):
            xi, yi = polygon[i]
            xj, yj = polygon[j]
            if (yi > y) != (yj > y):
                if yj != yi:
                    x_intersect = (xj - xi) * (y - yi) / (yj - yi) + xi
                    if x < x_intersect:
                        inside = not inside
            j = i
        return inside
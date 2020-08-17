import io
import re
import textwrap
import math
import time
import glob
import sys
import os
from PIL import Image, ImageDraw, ImageFont
from bs4 import BeautifulSoup


class Cell:
    """Una clase para no tener que usar dict y hacer más legible el
    código

    Atributos
    ---------
    colspan : int
        Cuántas columnas ocupa la celda.
    content : str
        El contenido de la celda.
    is_header : bool
        True si se trata de la primera fila y querés que se destaque.
    rowspan : int
        Cuántas filas ocupa la celda.
    css_width : str
        Ancho de la celda. Es str porque incluyo las unidades.
    row : int
        Número de fila a la que pertenece la celda.
    col : int
        Número de columna a la que pertenece la celda.
    """
    colspan = 1
    content = ""
    is_header = False
    rowspan = 1
    css_width = ""
    row = 0
    col = 0


class TableToIMG():
    """Una clase para parsear una tabla en HTML y generar una imagen.

    Atributos
    ---------
    font : ImageFont
        Fuente a utilizar.
    caption : str
        Título de la tabla. Puede setearse manualmente, o utilizar el 
        que se encuentre en el HTML (este último tiene precedencia).
    d : ImageDraw
        Objeto mediante el cual se realizan todos los gráficos.
    img : Image
        Objeto que guarda todos los gráficos, y permite generar la
        imagen final.
    font_name : str
        Path hacia la fuente TrueType que se quiera utilizar.
    logo : str
        Path hacia la imagen que se quiera utilizar como logo en el
        footer (PNG, 100x100).
    font_size : int
        Tamaño de fuente normal. De éste derivan algunos de los
        utilizados en el footer.
    median_char_width : int
        Valor utilizado para agilizar el cálculo del word wrap.
        Representa el ancho medio de los caracteres en la fuente que se
        está utilizando. Se setea automáticamente al llamar a __init__.
    spaces_re : re
        Objeto de expresión regular utilizado para eliminar espacios
        innecesarios en el contenido de una celda. Lo pongo acá para no
        tener que compilarlo con cada ciclo.
    width_re : re
        Objeto de expresión regular utilizado para obtener el ancho de
        una celda a partir del HTML. Ídem spaces_re.
    total_col_count : int
        Cantidad total de columnas de la tabla. Se setea
        automáticamente.
    total_row_count : int
        Cantidad total de filas de la tabla. Se setea automáticamente.
    row_heights : list[<int>]
        Lista con las alturas de cada fila. Se setea automáticamente.
    col_widths : list[<int>]
        Ídem, con los anchos de cada columna.
    cells : list[<Cell>]
        Lista de celdas.
    caption_box_height : int
        Altura, en píxeles, del título de la tabla.
    table_width : int
        Ancho del área reservada para la tabla.
    table_height : int
        Alto del área reservada para la tabla.
    footer_box_height : int
        Altura del área reservada para el footer.
    img_width : int
        Ancho de la imagen final.
    img_height : int
        Altura mínima de la imagen final. Se modifica si no entran todas
        las filas en el área reservada para la tabla.
    draw_borders : bool
        Determina si dibujar o no los bordes de las celdas.
    bg_color, fg_color, hd_color : (<int>, <int>, <int>)
        Valor RGB de los colores a utilizar para el color de fondo, del
        texto y de fondo de la primera fila, respectivamente.
    img_format : str
        Formato del archivo de salida. Tiene que ser soportado por PIL.
    draw_footer : bool
        Controla si dibujar o no el footer.
    footer_line_n : str
        Línea n del footer. La línea 2 utiliza el mismo tamaño de fuente
        que el resto de la tabla, mientras que 1 y 3 son un poco más
        pequeñas.
    """    
    font = None
    caption = ""
    d = None
    img = None
    font_name = ""
    logo = ""
    font_size = 24
    median_char_width = 1
    spaces_re = re.compile(r"(^\n)|(\n {2,})|(\n*$)|( {2,})", re.M)
    width_re = re.compile(r"width:(.*);?", flags=re.I)
    total_col_count = 0
    total_row_count = 0
    row_heights = []
    col_widths = []
    cells = []
    caption_box_height = 100
    table_width = 1800
    table_height = 780
    footer_box_height = 200
    img_width = 1920
    img_height = 1080
    draw_borders = True
    bg_color = (30, 30, 30)
    fg_color = (211, 211, 211)
    hd_color = (83, 149, 204)  # Azul
    img_format = "PNG"
    draw_footer = True
    footer_line_1 = ""
    footer_line_2 = ""
    footer_line_3 = ""


    def GetImage(self, raw_html: str, img_width: int, img_height: int) -> bytes:
        """Devuelvo los bytes de una imagen generada a partir de una
        tabla HTML.

        Parámetros
        ----------
        raw_html
            Tabla HTML a parsear
        img_width
            Ancho de la imagen final
        img_height
            Altura mínima de la imagen final. Se modifica
            automáticamente si no llegasen a entrar todas las filas.
        """

        self._ResetObj()
        self.img_height = img_height
        self.img_width = img_width
        self.table_height = img_height - self.caption_box_height - (0, self.footer_box_height)[self.draw_footer]
        self.table_width = img_width - 100
        self._CreateFontObj()

        self._ParseHTML(raw_html)
        
        self.img = Image.new(
            "RGB", (self.img_width, self.img_height), self.bg_color)
        self.d = ImageDraw.Draw(self.img)
        
        self._DrawHeader()
        self._DrawCells()
        if self.draw_footer:
            self._DrawFooter()

        imgByteArr = io.BytesIO()
        self.img.save(imgByteArr, self.img_format)

        return imgByteArr.getvalue()
    
    def _DrawFooter(self) -> None:
        """Dibujo el footer de la imagen.
        """
        font_1 = ImageFont.truetype(self.font_name, self.font_size + 10)
        font_2 = ImageFont.truetype(self.font_name, self.font_size)
        x0 = 50
        y0 = self.img_height - self.footer_box_height + 50
        x1 = x0 + 100
        y1 = y0 + 100

        # Dibujo el logo
        if os.path.exists(self.logo):
            logo = Image.open(self.logo)
            self.img.paste(self.fg_color, (x0, y0, x1, y1), logo)
        else:
            print("WARNING: No existe el archivo '%s'" % (self.logo))
        
        # Dibujo la línea separadora
        x0 = x1 + 10
        self.d.line([x0, y0, x0, y1], fill=self.fg_color, width=1)

        # Escribo el texto
        # Primera linea
        x0 = x0 + 11
        self.d.text((x0, y0), self.footer_line_1, fill=self.fg_color, font=font_2)
        # Segunda linea
        y0 += font_2.getsize(self.footer_line_1)[1] + 2
        self.d.text((x0, y0), self.footer_line_2, fill=self.fg_color, font=font_1)
        # Tercera linea
        y0 += font_1.getsize(self.footer_line_2)[1] + 2
        self.d.text((x0, y0), self.footer_line_3, fill=self.fg_color, font=font_2)
        return

    def _DrawHeader(self) -> None:
        header_font = ImageFont.truetype(self.font_name, self.font_size + 10)
        header_text_dimensions = header_font.getsize_multiline(self.caption.upper())

        if header_text_dimensions[1] > self.caption_box_height:
            print("WARNING: Caption demasiado alto", file=sys.stderr)
        
        x = int((self.img_width - header_text_dimensions[0]) / 2)
        y = int((self.caption_box_height - header_text_dimensions[1]) / 2)

        self.d.text([x, y], self.caption.upper(), font=header_font, fill=self.fg_color)

        return

    def _ResetObj(self) -> None:
        """Vuelvo a los valores por defecto del objeto.
        """
        self.d = None
        self.total_col_count = 0
        self.total_row_count = 0
        self.row_heights = []
        self.col_widths = []
        self.cells = []
        return

    def _CreateFontObj(self) -> None:
        """Creo el objeto de fuente según los atributos del objeto, y
        calculo la media de ancho de los caracteres.
        """
        # Creo la fuente
        self.font = ImageFont.truetype(self.font_name, self.font_size)
        # "b" representa el valor mediano de los caracteres
        self.median_char_width = self.font.getsize("b")[0]
        return

    def _ParseHTML(self, raw_html: str) -> None:
        """Parseo HTML y vuelco el resultado en self.cells.

        Parámetros
        ----------
        raw_html : str
            Tabla HTML a parsear.
        """
        # Cuento cantidad de columnas, filas
        # Lleno el objeto Cell
        # Agrego valores a row_heights, col_widths
        # Determino si es header
        # Ajusto los anchos proporcionalmente
        # Si el alto total de la tabla es demasiado, ajusto la dimensión
        # de la imagen
        parsed_html = BeautifulSoup(raw_html, features="html.parser")
        rows = parsed_html.find_all("tr")
        self.total_row_count = len(rows)

        caption_obj = parsed_html.find("caption")
        if caption_obj is not None:
            self.caption = caption_obj.text

        i = 0
        j = 0
        last_i = 0
        for row in rows:
            self.row_heights.append(0)
            cells = row.find_all(["td", "th"])

            for cell in cells:
                if i != last_i:
                    # Cambiamos de fila
                    self.total_col_count = max(self.total_col_count, j)
                    j = 0

                cell_obj = Cell()

                if "colspan" in cell.attrs:
                    cell_obj.colspan = int(cell.attrs["colspan"])
                if "rowspan" in cell.attrs:
                    cell_obj.rowspan = int(cell.attrs["rowspan"])
                if "width" in cell.attrs:
                    cell.width = cell.attrs["width"]
                if "style" in cell.attrs:
                    if cell.attrs["style"].find("width") != -1:
                        cell.width = self.width_re.findall(
                            cell.attrs["style"])[0]

                cell_obj.content = cell.text
                cell_obj.is_header = (cell.name == "th")
                cell_obj.row = i
                cell_obj.col = j

                self.cells.append(cell_obj)

                j += 1
                last_i = i
            i += 1
        
        # Por si solo tenemos una fila
        if j > self.total_col_count:
            self.total_col_count = j
        
        # Inicializo las listas
        self.col_widths = [0] * self.total_col_count
        self.row_heights = [0] * self.total_row_count
        
        # Calculo las dimensiones de las celdas
        last_i = 0
        std_cell_width = int(self.table_width / self.total_col_count)
        total_table_width = 0
        accumulated_width = 0
        for cell in self.cells:
            if cell.row != last_i:
                # Cambio de fila
                total_table_width = max(total_table_width, accumulated_width)
                accumulated_width = 0

            width = self._ConvertToPx(cell.css_width)
            if width == 0:
                width = std_cell_width
            # 1.3 convierte de pt a px
            height = int(self.font_size * 1.3)
            self.col_widths[cell.col] = max(
                self.col_widths[cell.col], width)
            self.row_heights[cell.row] = max(self.row_heights[cell.row], height)
            accumulated_width += width

        # Por si la tabla solo tiene una fila
        if total_table_width == 0:
            total_table_width = accumulated_width

        # Formateo el texto y ajusto el alto de fila si corresponde
        for cell in self.cells:
            cell.content = self._FormatField(
                cell.content, self.col_widths[cell.col] * cell.colspan)
            self.row_heights[cell.row] = max(
                self.row_heights[cell.row], self._GetCellHeight(cell.content))

        # Si el alto total de la tabla supera el predeterminado:
        if sum(self.row_heights) > self.table_height:
            # Redimensiono la imagen
            self.table_height = sum(self.row_heights)
            self.img_height = self.caption_box_height + self.table_height + (50, self.footer_box_height)[self.draw_footer]

        return

    def _ConvertToPx(self, val: str) -> int:
        """Convierto un tamaño de CSS a un entero en px.

        Parámetros
        ----------
        val : str
            Valor de CSS a convertir (ej.: "250pt")
        """
        px = 0

        if not len(val) == 0:
            if "%" in val:
                px = int(val[:-1]) * self.table_width / 100
            else:
                unit = val[-2:]  # "100px" --> "px"
                value = int(val[:-2].split(".")[0])
                conversion_factors = {
                    "px": 1,
                    "in": 96,
                    "pt": 1.3,
                    "pc": 16,
                    "cm": 38,
                    "mm": 3.8,
                    "em": self.font_size,
                    "vw": self.table_width,
                    "vh": self.table_height
                }

                if unit in conversion_factors:
                    px = value * conversion_factors[unit]
                else:
                    print("WARNING: No conozco la unidad '%s'" % (unit))

        return int(px)

    def _FormatField(self, text: str, width: int) -> str:
        """Elimino espacios de más, y hago el text wrap si es necesario.

        Parámetros
        ----------
        text : str
            Texto de la celda.
        width : int
            Ancho (en píxeles) de la celda.
        """
        text = text.replace(u"\xa0", "")
        text = self.spaces_re.sub("", text)
        if self._GetCellWidth(text) > width:
            text = self._WrapText(text, width)
        return text

    def _DrawCells(self) -> None:
        """Dibujo las celdas de self.cells.
        """
        # Para cada celda:
        # Si isHeader:
        # Dibujo el fondo de la celda
        # Si DrawBorders:
        # Dibujo el borde de la celda
        # Dibujo el texto centrado en la celda
        # Aumento los contadores de row, col
        last_x = int((self.img_width - self.table_width) / 2)
        last_y = self.caption_box_height
        last_row = 0
        for cell in self.cells:
            if cell.row != last_row:
                # Cambio de fila
                last_x = int((self.img_width - self.table_width) / 2)
                last_y = self.caption_box_height + sum(self.row_heights[0:cell.row])

            x0 = last_x
            y0 = last_y
            x1 = x0 + self.col_widths[cell.col] * cell.colspan
            y1 = y0 + self.row_heights[cell.row] * cell.rowspan

            if cell.is_header:
                self.d.rectangle([x0, y0, x1, y1], fill=self.hd_color)
            if self.draw_borders:
                self.d.rectangle([x0, y0, x1, y1], outline=self.fg_color)
            self.d.text((x0, y0), cell.content,
                        fill=self.fg_color, font=self.font)

            last_x = x1
            last_row = cell.row
        return

    def _GetCellWidth(self, content: str) -> int:
        """Wrapper para _GetCellDimension
        """
        return self._GetCellDimension(content, 0)

    def _GetCellHeight(self, content: str) -> int:
        """Wrapper para _GetCellDimension
        """
        return self._GetCellDimension(content, 1)

    def _GetCellDimension(self, content: str, param=0) -> int:
        """Calculo la dimensión requerida para que entre el texto,
        teniendo en cuenta la fuente y tamaño utilizados.

        Parámetros
        ----------
        content: str
            Texto de la celda.
        param : int
            Dimensión a calcular. Valores permitidos: 0 (ancho),
            1 (alto).
        """
        return self.font.getsize_multiline(content)[param]

    def _WrapText(self, text: str, width: int) -> str:
        """Hago el text wrap según qué tantos caracteres quepan en un
        determinado ancho de celda.

        Parámetros
        ----------
        text : str
            Texto de la celda.
        width : int
            Ancho de la celda.
        """
        max_chars = self._GetMaxChars(width)
        return "\n".join(textwrap.wrap(text, max_chars))

    def _GetMaxChars(self, width: int) -> int:
        """Devuelvo la cantidad de caracteres que entran en un
        determinado ancho de celda, según el tipo y tamaño de fuente.

        Parámetros
        ----------
        width : int
            Ancho de la celda.
        """
        cnt = max(math.floor(width / self.median_char_width), 1)
        return cnt


if __name__ == "__main__":
    t = TableToIMG()
    t.font_name = "assets/Montserrat-Regular.ttf"
    t.draw_footer = True
    t.logo = "assets/logo.png"
    t.footer_line_1 = "Twitter: @Test (cuenta no oficial)"
    t.footer_line_2 = "Municipalidad de General Pueyrredón"
    t.footer_line_3 = "Datos obtenidos de prueba"
    for file in glob.glob("tests/*.html"):
        print(file)
        start = time.time()
        with open(file, "rt") as fp:
            html = fp.read()
        t.caption = file
        img = t.GetImage(html, 1920, 1080)
        with open(file[:-4] + "png", "wb") as fp:
            fp.write(img)
        print("\tTerminado en %s s" % round(time.time() - start, 1))

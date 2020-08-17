import requests
import sys
import re
import os
import textwrap
import string
from random import choices
from HTMLtoImg import TableToIMG
from bs4 import BeautifulSoup

art_regex = re.compile(r"^\s*?art.culo\s*?(\d+).*?(?=\w)", flags=re.I)
spaces_regex = re.compile(r" {2,}")


class Tweet:
    """Una clase para hacer más legible el código"""

    def __init__(self, content="", media_filenames=[]) -> None:
        """
        Parámetros
        ----------
        content : str
            El texto del tweet
        media_filenames : list
            Una lista conteniendo los paths hacia las imágenes a incluir
            en el tweet
        """
        self.content = content
        self.media_filenames = media_filenames


class Publicacion:
    def __init__(self) -> None:
        self.articulos = []
        self.boid = 0
        self.ciudad_fecha = ""
        self.imagenes = []
        self.titulo = ""
        self.url = ""
        self.tablas = []
        self.cuits = []
        self.anexos = []

    def GetTweets(self) -> list:
        """Devuelvo una lista de objetos Tweet basados en el contenido 
        de la publicación
        """
        if not os.path.exists("temp"):
            os.mkdir("temp")

        fill = "... (sigue)"
        max_chars = 280 - len(fill)
        tweets = []
        first_tweet = self.ciudad_fecha + "\n" + self.titulo + \
            "\nFuente: %s" % (self.url) + \
            ("", " (ver anexos)")[len(self.anexos) > 0]
        first_tweet += "\nRecordá que esta cuenta no está afiliada al Municipio!"
        tweets.append(Tweet(first_tweet))
        for art in self.articulos:
            art = self._FormatText(art)
            if len(art) > max_chars:
                art = art[:max_chars] + fill
            tweets.append(Tweet(art, []))

        media_filenames = []
        for i in range(0, len(self.imagenes)):
            filename = "temp/%s.png" % (self._GetRandomString())
            with open(filename, "wb") as fp:
                fp.write(self.imagenes[i])

            # Separo cada 4 imágenes, que es el máximo que se puede
            # subir por cada Tweet.
            media_filenames.append(filename)
            if (i+1) % 4 == 0:
                tweets.append(Tweet(media_filenames=media_filenames))
                media_filenames = []

        if len(media_filenames) != 0 and len(media_filenames) % 4 != 0:
            # El último Tweet tiene menos de 4 imágenes, pero no está
            # vacío.
            tweets.append(Tweet(media_filenames=media_filenames))

        # os.rmdir("temp")

        return tweets

    def _FormatText(self, text: str) -> str:
        """Quito espacios innecesarios y hago un formateo básico del
        texto
        """
        text = text.replace(u"\xa0", " ")
        # La diferencia es extremadamente sutil, pero rompía art_regex
        text = text.replace(u"º", u"°")
        text = spaces_regex.sub(" ", text)
        # "Artículo 3˚.- Se dispone..." -> "3: Se dispone..."
        text = art_regex.sub(r"\1: ", text)

        return text

    def _GetRandomString(self) -> str:
        """Devuelvo una secuencia aleatoria de 10 caracteres para
        utilizar en los nombres de archivo.
        """
        return "".join(choices(string.ascii_letters + string.digits, k=10))


class SIBOM:
    sibom_url = "https://sibom.slyt.gba.gov.ar/bulletins/"
    img_gen = TableToIMG()
    muni_display = ""
    muni = ""
    tw_handle = ""
    muni_regex = None
    cuit_regex = re.compile(
        r"([23]\d *?- *?\d{7,8} *?- *?\d)", flags=re.I | re.M | re.S)

    def __init__(self, tw_handle: str, muni_display: str, muni_regex: str, font_name: str, logo: str) -> None:
        """
        Parámetros
        ----------
        tw_handle : str
            El nombre de usuario de Twitter que se utilizará. Lo uso
            para los pies de las imágenes que genero a partir de tablas.
        muni_display : str
            El nombre del municipio. También lo uso en las imágenes.
        muni_regex : str
            Una expresión regular para matchear el municipio en SIBOM.
            Hago de esta forma para contemplar casos en que el municipio
            contenga (o no) acentos o mayúsculas.
        font_name : str
            Path a una fuente TrueType a utilizar para las imágenes.
        logo : str
            Path al logo del municipio a utilizar (PNG, 100x100).
        """

        self.tw_handle = tw_handle
        self.muni_display = muni_display
        self.muni_regex = re.compile(muni_regex, re.IGNORECASE)
        self.img_gen.footer_line_1 = "Twitter: %s (cuenta no afiliada al municipio)" % (
            self.tw_handle)
        self.img_gen.footer_line_2 = "Municipalidad de %s" % (
            self.muni_display)
        self.img_gen.font_name = font_name
        self.img_gen.logo = logo

        return

    def _GetURL(self, url: str, **kwargs) -> BeautifulSoup:
        """Hago el request y devuelvo el objeto parseado por BS

        Parámetros
        ----------
        url : str
            URL a la cual acceder
        **kwargs
            Cualquier otro parámetro que se desee pasar a requests.get
        """
        # TODO: Reintentar un par de veces si falla
        parsed = None
        resp = requests.get(url, kwargs)

        if resp.status_code != 200:
            print("ERROR: No pude acceder a %s" % (url))
        else:
            parsed = BeautifulSoup(resp.text, features="html.parser")

        return parsed

    def GetLatestID(self) -> int:
        """Devuelvo el ID del último boletín oficial dado un municipio.

        Si no lo encuentro en las primeras cinco páginas, o no puedo
        acceder por algún motivo, devuelvo 0.
        """
        id = 0

        for i in range(1, 6):
            url = self.sibom_url + ("", "?page=%s" % (i))[i > 1]
            parsed = self._GetURL(url)

            if parsed:
                divs = parsed.find_all(class_="row bulletin-index")

                if divs is not None:
                    for div in divs:
                        if self.muni_regex.search(div.text):
                            # Encontré el div, obtengo el id
                            id = div.find("form").attrs["action"]
                            # "/bulletins/(id)" --> (id)
                            id = int(id.split("/")[2])
                            break
                    if id != 0:
                        break
        return id

    def GetAllURLs(self, id: int) -> list:
        """Devuelvo las URL de decretos, resoluciones, etc. de un BO

        Parámetros
        ----------
        id : int
            El ID del boletín oficial al que se desea acceder.
        """
        url = self.sibom_url + "%s?" % (id)
        urls = []
        parsed = self._GetURL(url)

        if parsed:
            objs = parsed.find_all("a", class_="content-link")
            for obj in objs:
                # "/bulletins/4047/contents/1477570" --> "1477570"
                bulletin_id = obj.attrs["href"].split("contents/")[1]
                url = self.sibom_url + "%s/contents/%s" % (id, bulletin_id)
                urls.append(url)
        return urls

    def ParsePublicacion(self, url: str) -> Publicacion:
        """Accedo a una URL y devuelvo los datos parseados

        Parámetros
        ----------
        url : str
            URL del decreto o resolución requerido.
        """
        pub = Publicacion()
        pub.tablas = []
        parsed = self._GetURL(url)

        if parsed:
            pub.titulo = parsed.find(class_="title").text
            pub.url = url
            pub.ciudad_fecha = parsed.find(class_="city-and-date").text

            contenido = parsed.find(class_="col-md-9")

            pub.cuits = self.cuit_regex.findall(contenido.text)
            # pub.tablas = contenido.find_all("table")
            pub.tablas = contenido.find_all(self._MatchTables)

            pub.anexos = []
            for anexo in parsed.find_all(class_="annex-name"):
                pub.anexos.append(anexo.text)

            for art in contenido.find_all(self._MatchParagraphs, recursive=False):
                pub.articulos.append(art.text)

            self.img_gen.caption = pub.titulo
            self.img_gen.footer_line_3 = "Datos extraídos de SIBOM. Fuente: %s" % (
                url)
            for tabla in pub.tablas:
                pub.imagenes.append(
                    self.img_gen.GetImage(str(tabla), 1920, 1080))

        return pub

    def _MatchParagraphs(self, tag: BeautifulSoup) -> bool:
        """Devuelvo True si un tag HTML corresponde a un artículo de una
        resolución o decreto. Utilizado con BeautifulSoup.

        Hago esto porque acostumbran no poner un atributo _class_, ni
        hacer ningún tipo de distinción en el código.

        Parámetros
        ----------
        tag : BeautifulSoup
            Objeto BeautifulSoup a evaluar.
        """
        matches = False
        if tag.name != "table":
            if art_regex.match(tag.text):
                # Comienza con "artículo"
                matches = True
        return matches

    def _MatchTables(self, tag: BeautifulSoup) -> bool:
        """Devuelvo True si un tag HTML corresponde a una tabla.

        Tengo que hacer esto porque acostumbran poner tablas, dentro de 
        tablas, dentro de tablas... Con este método determino si se 
        trata de la última capa de la cebolla.

        De no hacerlo de esta manera, en algunos casos TableToIMG
        tardaba muchísimo en procesar todo, y devolvía basura.

        Parámetros
        ----------
        tag : BeautifulSoup
            Objeto BeautifulSoup a evaluar.
        """
        matches = False
        if tag.name == "table":
            if not tag.find("table"):
                # Por si la tabla está vacía...
                if not len(tag.text.strip("\n\xa0 ")) == 0:
                    matches = True
        return matches


if __name__ == "__main__":
    s = SIBOM("@BoletinMGP", "General Pueyrredón",
              r"general pueyrred.n", "assets/Montserrat-Regular.ttf", "assets/logo.png")

    id = s.GetLatestID()

    if id != 0:
        print("Procesando %s..." % id)

        urls = s.GetAllURLs(id)

        if not os.path.exists(str(id)):
            os.mkdir(str(id))

        for url in urls:
            print("\t" + url)
            pub = s.ParsePublicacion(url)
            tweets = pub.GetTweets()
            filename = pub.titulo.replace("/", "")
            with open("%s/%s.txt" % (id, filename), "wt") as fp:
                for tw in tweets:
                    if len(tw.content) > 0:
                        fp.write(tw.content + "\n" + "-" * 20 + "\n")
                    if len(tw.media_filenames) > 0:
                        fp.write(str(tw.media_filenames) +
                                 "\n" + "-" * 20 + "\n")

    # for id in [3987]:  # [3970,3987,4009,4012,4016,4047]:
    #     print("Procesando %s..." % id)

    #     urls = s.GetAllURLs(id)

    #     if not os.path.exists(str(id)):
    #         os.mkdir(str(id))

    #     for url in urls:
    #         print("\t" + url)
    #         pub = s.ParsePublicacion(url)
    #         tweets = pub.GetTweets()
    #         filename = pub.titulo.replace("/", "")
    #         with open("%s/%s.txt" % (id, filename), "wt") as fp:
    #             for tw in tweets:
    #                 if len(tw.content) > 0:
    #                     fp.write(tw.content + "\n" + "-" * 20 + "\n")
    #                 if len(tw.media_filenames) > 0:
    #                     fp.write(str(tw.media_filenames) +
    #                              "\n" + "-" * 20 + "\n")

import requests
import json
import urllib

import sys
import threading
import subprocess

from PyQt5.QtCore import *
from PyQt5.QtWidgets import *
from PyQt5.QtGui import *

class HearthstoneApi:
    def __init__(self, url, key):
        self.url = url
        self.key = key

        self.load_cards()

    def load_cards(self):
        response = requests.get(self.url,
          headers={
            "X-Mashape-Key": self.key
          }
        )
        self.cards = json.loads(response.text)

    def find_cards(self, name, mana_cost = None):
        found_cards = []
        for key, expansion in self.cards.items():
            if key == 'Debug':
                continue

            for card in expansion:
                if card['name'].lower().startswith(name.lower()) and "cost" in card:
                    found_cards.append(card)
        return found_cards


class LogWatcher(QThread):

    card_action = pyqtSignal(object, object)

    def __init__(self, log_path):
        QThread.__init__(self)
        self.log_path = log_path

    def process_line(self, card_name, action):
        self.card_action.emit(card_name, action)

    def run(self):
        p = subprocess.Popen(["tail", "-f", self.log_path], stdout=subprocess.PIPE)
        while 1:
            line = p.stdout.readline().decode('utf-8')
            # Turn 1 draws
            if line.startswith("[Zone] ZoneChangeList.ProcessChanges() - id=1 ") and "zone from  -> FRIENDLY HAND" in line:
                if "name=" in line:
                    print(line)
                    start = line.find("name=")
                    end = line.rfind(" id")
                    card = line[start+5:end]
                    if card == "The Coin":
                        continue

                    print(card)
                    self.process_line(card, "hand")
            elif line.startswith("[Zone] ZoneChangeList.ProcessChanges() -"):
                if "name=" in line:
                    print(line)
                    start = line.find("name=")
                    end = line.rfind(" id")
                    card = line[start+5:end]

                    if "FRIENDLY DECK ->" in line:
                        print("FRIENDLY HAND")
                        self.process_line(card, "hand")
                    elif "-> FRIENDLY DECK" in line:
                        print("FRIENDLY DECK")
                        self.process_line(card, "deck")
                    elif "FRIENDLY PLAY -> FRIENDLY GRAVEYARD" in line:
                        print("GY")
                        self.process_line(card, "gy")
                    elif card == "Excavated Evil" and "zone from  -> OPPOSING GRAVEYARD" in line:
                        print("FRIENDLY DECK")
                        self.process_line(card, "deck")
                elif "GameAccountId=" in line:
                    print("Processing line.")
                    self.process_line({}, "reset")

class CreateDeckWidget(QWidget):
    def __init__(self, hs_api, parent=None):
        super(CreateDeckWidget, self).__init__(parent)

        self.hs_api = hs_api
        self.current_search = []

        self.search_bar = QLineEdit(self)
        self.search_button = QPushButton("Search")
        self.search_button.clicked.connect(self.search)

        self.deck_list = QListView()
        self.deck_list.doubleClicked.connect(self.add_card)
        self.deck_list.setEditTriggers(QAbstractItemView.NoEditTriggers)

        self.deck_builder_layout = QVBoxLayout()

        self.deck_builder_layout.addWidget(self.search_bar)
        self.deck_builder_layout.addWidget(self.search_button)
        self.deck_builder_layout.addWidget(self.deck_list)

        self.current_deck = QListView()
        self.current_deck.doubleClicked.connect(self.remove_card)
        self.current_deck.setEditTriggers(QAbstractItemView.NoEditTriggers)

        self.current_deck_model = QStandardItemModel(self.current_deck);
        self.current_deck.setModel(self.current_deck_model)

        self.deck_count = QLabel()
        self.deck_count.setText("0")

        self.load_button = QPushButton("Load")
        self.load_button.clicked.connect(self.load_deck)
        self.save_button = QPushButton("Save")
        self.save_button.clicked.connect(self.save_deck)

        self.load_save_layout = QHBoxLayout()
        self.load_save_layout.addWidget(self.load_button)
        self.load_save_layout.addWidget(self.save_button)

        self.current_deck_layout = QVBoxLayout()
        self.current_deck_layout.addWidget(self.deck_count)
        self.current_deck_layout.addWidget(self.current_deck)
        self.current_deck_layout.addLayout(self.load_save_layout)

        main_layout = QGridLayout()

        main_layout.addLayout(self.deck_builder_layout, 0,0)
        main_layout.addLayout(self.current_deck_layout, 0,1)

        self.setLayout(main_layout)
    
    def search(self):
        self.current_search = self.hs_api.find_cards(self.search_bar.text())

        self.search_model = QStandardItemModel(self.deck_list)
        for card in self.current_search:
            if not "cost" in card:
                continue

            item = QStandardItem()
            item.setText(card['name'])
            item.setData(card)

            self.search_model.appendRow(item)
        self.deck_list.setModel(self.search_model)
        self.deck_list.show()

    def add_card(self, index):
        if int(self.deck_count.text()) >= 30:
            return

        item = self.search_model.itemFromIndex(index)

        l = self.current_deck_model.findItems(item.text(), Qt.MatchEndsWith)
        if len(l):
            if l[0].text().startswith("2"):
                return
            l[0].setText("2 - " + item.text())
        else:
            new_item = QStandardItem()
            new_item.setText("1 - " + item.text())
            new_item.setData(item.data())
            self.current_deck_model.appendRow(new_item)

        new_count = int(self.deck_count.text()) + 1
        self.deck_count.setText(str(new_count))


    def remove_card(self, index):
        item = self.current_deck_model.itemFromIndex(index)
        t = item.text()
        if t[0] == "2":
            t_list = list(t)
            t_list[0] = '1'
            item.setText("".join(t_list))
        else:
            self.current_deck_model.removeRow(index.row())

        new_count = int(self.deck_count.text()) - 1
        self.deck_count.setText(str(new_count))

    def load_deck(self):
        dialog = QFileDialog(self, "Load Deck", ".", filter="*")
        dialog.setAcceptMode(QFileDialog.AcceptOpen)
        dialog.fileSelected.connect(self.load)
        dialog.open()

        pass
    def save_deck(self):
        dialog = QFileDialog(self, "Save Deck", ".", filter="*")
        dialog.setAcceptMode(QFileDialog.AcceptSave)
        dialog.fileSelected.connect(self.save)
        dialog.open()

    def save(self, deck_file):
        deck = []
        for index in range(0, self.current_deck_model.rowCount()):
            model_index = self.current_deck_model.index(index, 0)
            item = self.current_deck_model.itemFromIndex(model_index)
            card = {}
            card['count'] = item.text()[0]
            card['card'] = item.data()
            deck.append(card)
        print(deck)

        b = json.dumps({'deck' : deck})
        with open(deck_file, "w") as f:
            f.write(b)

    def load(self, deck_file):
        try:
            with open(deck_file, "r") as f:
                deck = json.loads(f.read())
        except Exception as e:
            print("Failed loading deck file.")
            raise e

        self.current_deck_model.clear()
        self.deck_count.setText("0")

        for card in deck["deck"]:
            new_item = QStandardItem()
            new_item.setText(card['count'] + " - " + card['card']['name'])
            new_item.setData(card['card'])
            self.current_deck_model.appendRow(new_item)

            new_count = int(self.deck_count.text()) + int(card['count'])
            self.deck_count.setText(str(new_count))

def draw_text_on_pixmap(pixmap, text, x, y, size, weight):
    font = QFont("PassionOne", size, weight, True)
    font.setBold(True)
    painter = QPainter()
    path = QPainterPath()
    pen = QPen()
    pen.setWidth(4)

    painter.begin(pixmap)
    painter.setFont(font)
    painter.setRenderHint(QPainter.Antialiasing)
    path.addText(x, y, font,text)
    painter.fillPath(path, QColor(Qt.white))
    painter.strokePath(path, QColor(Qt.black))
    painter.end()

class CardWidget(QWidget):
    def __init__(self, card, parent=None):
        super(CardWidget, self).__init__(parent)

        self.card = card

        url = card["card"]['img'].replace('original', 'medium')
        data = urllib.request.urlopen(url).read()
        image = QImage()
        image.loadFromData(data)

        self.card_pic = QPixmap(image)

        mana_rect = QRect(10,39,43,43)
        self.mana_pic = self.card_pic.copy(mana_rect).scaled(35, 35, Qt.IgnoreAspectRatio, Qt.FastTransformation)

        name_rect = QRect(16,84,164,43)
        self.card_name_pic = self.card_pic.copy(name_rect).scaled(164, 35, Qt.IgnoreAspectRatio, Qt.FastTransformation)

        draw_text_on_pixmap(self.card_name_pic, self.card["card"]["name"], 10,25,14,8)

        self.color = QColor(Qt.green)

        name_lbl = QLabel(self)
        name_lbl.setPixmap(self.card_name_pic)
        name_lbl.setStyleSheet("QLabel { background-color: #000000 }")
        name_lbl.setSizePolicy(QSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed))
        name_lbl.setContentsMargins(2,2,2,2)

        mana_lbl = QLabel(self)
        mana_lbl.setPixmap(self.mana_pic)
        mana_lbl.setStyleSheet("QLabel { background-color: #000000 }")
        mana_lbl.setContentsMargins(2,2,2,2)
        mana_lbl.setSizePolicy(QSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed))

        self.count_lbl = QLabel(self)
        self.count_lbl.setPixmap(self.create_count())
        self.count_lbl.setStyleSheet("QLabel { background-color: #000000 }")
        self.count_lbl.setContentsMargins(2,2,2,2)
        self.count_lbl.setSizePolicy(QSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed))

        hbox = QHBoxLayout(self)
        hbox.setContentsMargins(0,0,0,0)
        hbox.setSpacing(0)
        hbox.setSizeConstraint(QLayout.SetFixedSize)
        hbox.addWidget(mana_lbl, alignment=Qt.AlignLeft)
        hbox.addWidget(name_lbl, alignment=Qt.AlignLeft)
        hbox.addWidget(self.count_lbl, alignment=Qt.AlignLeft)

        self.setContentsMargins(0,0,0,0)
        self.setSizePolicy(QSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed))

        self.setLayout(hbox)
        self.show()
    
    def cost(self):
        return self.card["card"]["cost"]

    def id(self):
        return self.card["card"]["cardId"]

    def update_count(self, i):
        current_count = int(self.card["current_count"]) + i
        if current_count >= 0:
            self.card["current_count"] = str(current_count)
            new_count = self.create_count()
            self.count_lbl.setPixmap(new_count)

    def create_count(self):
        #font.setFamily('Lucida')
        #font.setPointSize(20)

        rect = QRect(0,0,50,35)
        pixmap = QPixmap(rect.width(), rect.height())

        count = int(self.card["current_count"])
        if count == 0:
            pixmap.fill(QColor(210, 27,57))
        elif count != int(self.card["count"]):
            pixmap.fill(QColor(122, 122, 29))
        else:
            pixmap.fill(QColor(36,36,41))

        draw_text_on_pixmap(pixmap, self.card["current_count"],16,27,25,40)

        return pixmap


class Deck(QWidget):
    def __init__(self, parent=None):
        super(Deck, self).__init__(parent)
        
        # List of CardWidgets. Sorted on mana cost
        self.deck = []

        self.original_deck = []

        self.vbox = QVBoxLayout(self)
        self.vbox.setContentsMargins(0,0,0,0)
        self.vbox.setSpacing(0)
        self.vbox.setSizeConstraint(QLayout.SetFixedSize)
        self.setLayout(self.vbox)

    def remove_card(self, card):
        print("attempting to remove:")
        print(card)
        for c in self.deck:
            if c.id() == card["cardId"]:
                print("Removing card from deck:" + card["name"])
                c.update_count(-1)
                break

    def add_card(self, card):
        print("attempting to add:")
        print(card)
        for c in self.deck:
            if c.id() == card["cardId"]:
                print("Updating card to deck:" + card["name"])
                c.update_count(1)
                return

        print("Updating new card to deck:" + card["name"])
        self.add_new_card({'card':card,'count':"1",'current_count':"1"})
        self.update_deck()

        
    def add_new_card(self, card):
        print("Adding new card to deck:" + card["card"]["name"])
        card["current_count"] = card["count"]
        self.deck.append(CardWidget(card))

    def add_original_card(self, card):
        print("Adding original card to deck:" + card["card"]["name"])
        card["current_count"] = card["count"]
        self.deck.append(CardWidget(card))
        self.original_deck.append(card)

    def update_deck(self):
        d = sorted(self.deck, key=lambda card: card.cost())
        self.deck = d

        self.clear_layout()

        for card in self.deck:
            self.vbox.addWidget(card)

        self.update()

    def clear_layout(self):
        while self.vbox.count():
            self.vbox.takeAt(0)

    ''' .'''
    def clear_deck(self):
        self.clear_layout()
        for card in self.deck:
            card.close()
        self.deck.clear()

    def clear_all(self):
        ''' Clear all data from deck, all original cards are removed.'''
        self.clear_deck()
        self.original_deck.clear()

    def reset(self):
        ''' Remove all cards that are not part of original deck.'''
        print("RESET")
        self.clear_deck()
        for card in self.original_deck:
            self.add_new_card(card)
        self.update_deck()

def set_button_color(button):
    pal = button.palette()
    pal.setColor(QPalette.Button, QColor(36,36,41))
    button.setAutoFillBackground(True)
    button.setPalette(pal)
    button.update()



class Application(QWidget):
    def __init__(self, parent=None):
        super(Application, self).__init__(parent)

        self.hs_api = HearthstoneApi("https://omgvamp-hearthstone-v1.p.mashape.com/cards", "xheCZlY9rKmshpNX8bKzZZu9OXLop16ppZpjsnLLmgFYvLVsA5")

        self.deck = Deck()


        self.load_deck_button = QPushButton("Import")
        self.load_deck_button.clicked.connect(self.load_deck)
        set_button_color(self.load_deck_button)

        self.reset = QPushButton("Reset")
        self.reset.clicked.connect(self.deck.reset)
        set_button_color(self.reset)

        self.create_deck = QPushButton("Create")
        self.create_deck.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.create_deck.clicked.connect(self.create)
        set_button_color(self.create_deck)

        self.gy = QPushButton("GY")
        self.gy.clicked.connect(self.toggle_gy)
        set_button_color(self.gy)


        # Menu layout
        self.menu_layout = QHBoxLayout()
        self.menu_layout.setContentsMargins(0,0,0,0)
        self.menu_layout.setSpacing(0)
        self.menu_layout.addWidget(self.gy)
        self.menu_layout.addWidget(self.load_deck_button)
        self.menu_layout.addWidget(self.create_deck)
        # self.menu_layout.addWidget(self.reset)

        # Current deck layout
        self.play_deck_layout = QVBoxLayout()
        self.play_deck_layout.setContentsMargins(0,0,0,0)
        self.play_deck_layout.setSpacing(0)
        self.play_deck_layout.setSizeConstraint(QLayout.SetFixedSize)
        self.play_deck_layout.addLayout(self.menu_layout)
        self.play_deck_layout.addWidget(self.deck)

        # Create deck widget.
        self.create_deck_widget = CreateDeckWidget(self.hs_api)
        self.create_deck_widget.setHidden(True)

        # Graveyard
        self.graveyard = Deck()
        self.graveyard.add_card(self.hs_api.find_cards("forbidden")[0])
        self.graveyard.setHidden(True)

        self.create_deck_layout = QHBoxLayout()
        self.create_deck_layout.addWidget(self.create_deck_widget)

        main_layout = QGridLayout()
        main_layout.setContentsMargins(0,0,0,0)
        main_layout.setSpacing(0)
        main_layout.setSizeConstraint(QLayout.SetFixedSize)
        main_layout.addLayout(self.play_deck_layout, 0,0)
        main_layout.addLayout(self.create_deck_layout, 0,1)
        main_layout.addWidget(self.graveyard,0,2)

        self.setSizePolicy(QSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed))
        self.setContentsMargins(0,0,0,0)

        self.setLayout(main_layout)

        self.log_watcher= LogWatcher("/home/jens/.wine_bnet/drive_c/Program Files (x86)/Hearthstone/Hearthstone_Data/output_log.txt")
        self.log_watcher.card_action.connect(self.update)
        self.log_watcher.start()

    def toggle_gy(self):
        if not self.graveyard.isVisible():
            self.graveyard.setHidden(False)
        else:
            self.graveyard.setHidden(True)
        

    def create(self):
        if not self.create_deck_widget.isVisible():
            self.create_deck_widget.setHidden(False)
            self.create_deck.setText("Hide deck")
        else:
            self.create_deck_widget.setHidden(True)
            self.create_deck.setText("Create deck")

    def load_deck(self):
        dialog = QFileDialog(self, "Load Deck", ".", filter="*")
        dialog.setAcceptMode(QFileDialog.AcceptOpen)
        dialog.fileSelected.connect(self.load)
        dialog.open()

    def update(self, card_name, card_action):
        ''' Update from config.'''

        print("update")

        try:
            if card_action == "deck":
                card = self.hs_api.find_cards(card_name)[0]
                self.deck.add_card(card)
            elif card_action == "gy":
                card = self.hs_api.find_cards(card_name)[0]
                self.graveyard.add_card(card)
            elif card_action == "hand":
                card = self.hs_api.find_cards(card_name)[0]
                self.deck.remove_card(card)
            elif card_action == "reset":
                self.deck.reset()
                self.graveyard.clear_all()
        except Exception as e:
            pass

        return

    def load(self, filename):
        try:
            with open(filename, "r") as f:
                deck = json.loads(f.read())
        except Exception as e:
            print("Failed loading deck file.")
            raise e

        l = deck["deck"]
        for card in l:
            if not "cost" in card["card"]:
                print("MISSING COST")
                print(card["card"])
        sorted_deck  = sorted(l, key=lambda card: card["card"]["cost"])

        self.deck.clear_all()
        self.graveyard.clear_all()
        for index in range(0, len(sorted_deck)):
            card = sorted_deck[index]
            self.deck.add_original_card(card)
        self.deck.update_deck()
        

app = QApplication(sys.argv)

screen = Application()
screen.show()

sys.exit(app.exec_())

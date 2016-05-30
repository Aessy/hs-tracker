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
            if line.startswith("[Zone] ZoneChangeList.ProcessChanges() - TRANSITIONING card"):
                if "name=" in line:
                    start = line.find("name=")
                    end = line.find(" id")
                    card = line[start+5:end]

                    if "FRIENDLY HAND" in line:
                        print("FRIENDLY HAND")
                        print(line)
                        self.process_line(card, "hand")
                    if "FRIENDLY DECK" in line:
                        print("FRIENDLY DECK")
                        print(line)
                        self.process_line(card, "deck")

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
        print("remove card")
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


class CardWidget(QWidget):
    def __init__(self, card, parent=None):
        super(CardWidget, self).__init__(parent)
        print(card)

        self.card = card

        url = card["card"]['img'].replace('original', 'medium')
        data = urllib.request.urlopen(url).read()
        image = QImage()
        image.loadFromData(data)

        self.card_pic = QPixmap(image)

        mana_rect = QRect(10,39,43,43)
        self.mana_pic = self.card_pic.copy(mana_rect)

        name_rect = QRect(16,150,164,43)
        self.card_name_pic = self.card_pic.copy(name_rect)

        self.color = QColor(Qt.green)


        name_lbl = QLabel(self)
        name_lbl.setPixmap(self.card_name_pic)
        name_lbl.setStyleSheet("QLabel { background-color: #000000 }")
        name_lbl.setSizePolicy(QSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed))
        name_lbl.setContentsMargins(2,2,2,2)
        #name_lbl.setMinimumWidth(50)

        mana_lbl = QLabel(self)
        mana_lbl.setPixmap(self.mana_pic)
        mana_lbl.setStyleSheet("QLabel { background-color: #000000 }")
        mana_lbl.setContentsMargins(2,2,2,2)
        #mana_lbl.setMinimumWidth(50)
        mana_lbl.setSizePolicy(QSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed))

        count_lbl = QLabel(self)
        count_lbl.setPixmap(self.create_count())
        count_lbl.setStyleSheet("QLabel { background-color: #000000 }")
        count_lbl.setContentsMargins(2,2,2,2)
        count_lbl.setSizePolicy(QSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed))

        hbox = QHBoxLayout(self)
        hbox.setContentsMargins(0,0,0,0)
        hbox.setSpacing(0)
        hbox.setSizeConstraint(QLayout.SetFixedSize)
        hbox.addWidget(mana_lbl, alignment=Qt.AlignLeft)
        hbox.addWidget(name_lbl, alignment=Qt.AlignLeft)
        hbox.addWidget(count_lbl, alignment=Qt.AlignLeft)
        self.setLayout(hbox)
        self.show()

    def create_count(self):
        font = QFont()
        font.setFamily('Lucida')
        font.setPointSize(20)

        rect = QRect(0,0,43,43)
        pixmap = QPixmap(rect.width(), rect.height())
        pixmap.fill(QColor(0,0,51))

        painter = QPainter()
        painter.begin(pixmap)
        painter.setPen(QPen(QColor(Qt.white),1,Qt.SolidLine))
        painter.setBrush(self.color)
        painter.setFont(font)
        painter.drawText(0, 0, 43, 43, Qt.AlignCenter, str(self.card["count"]))
        painter.end()

        return pixmap


class Deck(QWidget):
    def __init__(self, parent=None):
        super(Deck, self).__init__(parent)
        
        # List of CardWidgets. Sorted on mana cost
        self.deck = []

        self.vbox = QVBoxLayout(self)
        self.setLayout(self.vbox)

    def add_card(self, card):
        card["current_count"] = card["count"]
        self.play_deck_layout.addWidget(CardWidget(card))



class Application(QWidget):
    def __init__(self, parent=None):
        super(Application, self).__init__(parent)

        self.hs_api = HearthstoneApi("https://omgvamp-hearthstone-v1.p.mashape.com/cards", "xheCZlY9rKmshpNX8bKzZZu9OXLop16ppZpjsnLLmgFYvLVsA5")

        self.load_deck_button = QPushButton("Load Deck")
        self.load_deck_button.clicked.connect(self.load_deck)

        self.reset = QPushButton("Reset")
        self.create_deck = QPushButton("Create Deck")

        self.create_deck.clicked.connect(self.create)

        self.menu_layout = QHBoxLayout()
        self.menu_layout.addWidget(self.load_deck_button)
        self.menu_layout.addWidget(self.reset)
        self.menu_layout.addWidget(self.create_deck)

        self.deck_model = QStandardItemModel(0,3)
        self.deck_model.setHorizontalHeaderLabels(['Cost', 'Name', 'Count'])

        self.play_deck_list = QListView()
        self.play_deck_list.setModel(self.deck_model)

        self.deck_layout = QVBoxLayout()


        self.play_deck_layout = QVBoxLayout()
        self.play_deck_layout.setContentsMargins(0,0,0,0)
        self.play_deck_layout.setSpacing(0)
        self.play_deck_layout.addLayout(self.menu_layout)
        self.play_deck_layout.addLayout(self.deck_layout)


        self.create_deck_widget = CreateDeckWidget(self.hs_api)
        self.create_deck_widget.setHidden(True)

        self.create_deck_layout = QHBoxLayout()
        self.create_deck_layout.addWidget(self.create_deck_widget)

        # self.a_test_card = CardWidget(self.hs_api.find_cards("forbidden shap")[0])

        main_layout = QGridLayout()
        main_layout.addLayout(self.play_deck_layout, 0,0)
        main_layout.addLayout(self.create_deck_layout, 0,1)
        #main_layout.addWidget(self.a_test_card, 1, 0)
        self.setLayout(main_layout)

        self.log_watcher= LogWatcher("/home/jens/.PlayOnLinux/wineprefix/WorldOfWarcraft/drive_c/Program Files/Hearthstone/Hearthstone_Data/output_log.txt")
        self.log_watcher.card_action.connect(self.update)
        self.log_watcher.start()

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

    def create_card_string(self, card, count):
        s = str(card['cost']) + " - " + card['name'] + " - " + str(count)
        return s

    def update(self, card_name, card_action):
        print("update")

        found = False

        addition = -1

        if card_action == "deck":
            addition = 1

        for index in range(0, self.deck_model.rowCount()):
            model_index = self.deck_model.index(index, 0)
            item = self.deck_model.itemFromIndex(model_index)

            print(item.text())

            card = item.data()


            print(card_name.lower())
            print(card['card']['name'].lower())
            if card_name.lower() == card['card']['name'].lower():
                print(card["current_count"])
                count = str(int(card['current_count']) + addition)
                card['current_count'] = count
                item.setText(self.create_card_string(card["card"], card["current_count"]))
                item.setData(card)
                if card["current_count"] == "1":
                    item.setBackground(QColor("yellow"))
                elif card["current_count"] == "0":
                    item.setBackground(QColor("red"))
                addition = 0
                break

        if addition == 1:
            print("ADDING NEW CARD")
            cards = self.hs_api.find_cards(card_name)
            card = cards[0]

            self.add_card({"card":card, "count":1,"current_count":1})
        self.repaint()

    def add_card(self, card):
        card["current_count"] = card["count"]
        self.play_deck_layout.addWidget(CardWidget(card))


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
        self.deck_model.clear()
        for index in range(0, len(sorted_deck)):
            card = sorted_deck[index]
            self.add_card(card)
        

app = QApplication(sys.argv)

screen = Application()
screen.show()

sys.exit(app.exec_())

from comtypes import CLSCTX_ALL
from ctypes import cast, POINTER
import cv2
import io
import json
from keras.models import load_model
import math
import matplotlib.pyplot as plt
import mediapipe as mp
import networkx as nx
import numpy as np
import os
import pyautogui
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
from PyQt5 import QtCore
from PyQt5.QtGui import QPixmap, QImage, QIcon
from PyQt5.QtCore import QThread, QThread, pyqtSignal
from PyQt5.QtWidgets import QComboBox, QApplication, QMainWindow, QLabel, QPushButton, QCheckBox, QSlider, QAbstractItemView
from PyQt5.QtMultimedia import QCameraInfo
import sys
import subprocess
import time
import webbrowser

pyautogui.FAILSAFE = False

class VideoCaptureThread(QThread):
    frameCaptured = pyqtSignal(QImage)
    handImage = pyqtSignal(QImage)
    summary = pyqtSignal(str)
    change_mouse_sinal = pyqtSignal(bool)

    def __init__(self, mp_config=None, parent=None):
        super().__init__()

        with open('config/config.json') as f:
            self.data = json.load(f)

        self.draw_points = self.data["exibicao"]["exibir_pontos"]
        self.draw_hand_limits = self.data["exibicao"]["exibir_limites"]
        self.agir = self.data["exibicao"]["navegar"]
        self.cam_indice = self.data["video"]["entrada"]
        self.alpha = self.data["video"]["saturacao"]
        self.beta = self.data["video"]["brilho"]

        self.cap = cv2.VideoCapture(self.cam_indice)
        self.model = self.load_model()

        self.video_record_run = False
        self.video_frame = -1
        self.tempo_atual = 0
        self.tempo_anterior = 0

        self.intervalo = 100
        self.intervalo_inicial = 500

        self.video = []
        
        self.movesAction = [ "FecharTelas", "PrintScreen", "AtivarModoMouseVirtual", "AumentarVolume", "IrParaCanalPredileto", "AbrirExploradorDeArquivos", "DiminuirVolume", "AumentarBrilho", "DiminuirBrilho", "AbrirNetflix", "AbrirDisneyPlus", "Confirmar"]
        self.controler = action()

        self.draw_hand_image = False
        self.mode_mouse = False
        self.change_mouse = False
        
        self.status = False
        self.mp_config = mp_config or {}
        self.mp_hands = mp.solutions.hands
        self.mp_draw = mp.solutions.drawing_utils
        self.screen_width, self.screen_height = pyautogui.size()
        self.hand_Landmarks = None
        self.prev_hand = None
        self.right_clicked = False
        self.left_clicked = False
        self.double_clicked = False
        self.dragging = False
        self.little_finger_down = None
        self.little_finger_up = None
        self.index_finger_down = None
        self.index_finger_up = None
        self.middle_finger_down = None
        self.middle_finger_up = None
        self.ring_finger_down = None
        self.ring_finger_up = None
        self.Thump_finger_down = None
        self.Thump_finger_up = None
        self.all_fingers_down = None
        self.all_fingers_up = None
        self.index_finger_within_Thumb_finger = None
        self.middle_finger_within_Thumb_finger = None
        self.little_finger_within_Thumb_finger = None
        self.ring_finger_within_Thumb_finger = None

        self.last_summary = time.time() * 1000

    def run(self):
        while True:
            sucesso, captura = self.cap.read()
            if not sucesso:
                continue

            captura = cv2.flip(captura, 1)

            frame, coordenadas, results = self.__getCoordinates(captura)
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            height, width, channel = frame.shape
            step = channel * width
            qImg = QImage(frame.data, width, height, step, QImage.Format_RGB888)
            self.frameCaptured.emit(qImg)

            # if self.draw_hand_image:
            #     self.drawHand(coordenadas)

            #     self.draw_hand_image = False
        
            self.tempo_atual = time.time() * 1000

            if self.tempo_atual - self.last_summary >= 2000:
                self.summary.emit("")

            if self.change_mouse:
                self.change_mouse = False

                if self.mode_mouse:
                    self.stopMouseMode()
                else: 
                    self.activateMouseMode()

            if self.video_record_run == True:
                if self.video_frame == 0:
                    if self.tempo_atual - self.tempo_anterior > self.intervalo_inicial:
                        self.video.append(coordenadas)
                        self.video_frame = 1

                        self.tempo_anterior = time.time() * 1000

                elif self.video_frame > 0 and self.video_frame < 20:
                    if self.tempo_atual - self.tempo_anterior > self.intervalo:
                        self.video.append(coordenadas)
                        self.video_frame += 1

                        self.tempo_anterior = time.time() * 1000

                elif self.video_frame > 0 and self.video_frame == 20:
                    if self.tempo_atual - self.tempo_anterior > self.intervalo:
                        self.video.append(coordenadas)
                        self.video_frame = -1
                        self.video_record_run = False

                        self.video = np.array(self.video)

                        self.draw_hand_image = True

                        if self.agir:
                            self.predict(self.video)

                        self.video = []
            elif not self.mode_mouse:
                self.searchOrder(coordenadas)
            else:
                self.mouse(results)

    def __getCoordinates(self, frame):
        w, h, _ = frame.shape
        maos = self.mp_hands.Hands(max_num_hands=1)

        imagem = cv2.convertScaleAbs(frame, alpha=self.alpha, beta=self.beta)

        x, y, w, h = 0, 0, 0, 0
        
        resultados = maos.process(cv2.cvtColor(imagem, cv2.COLOR_BGR2RGB))

        lista_pontos = []

        if resultados.multi_hand_landmarks:
            for pontos_mao in resultados.multi_hand_landmarks:
                for ponto in pontos_mao.landmark:
                    altura, largura, _ = frame.shape
                    cx, cy = int(ponto.x * largura), int(ponto.y * altura)
                    lista_pontos.append((cx, cy))

                if lista_pontos:
                    x, y, w, h = cv2.boundingRect(np.array(lista_pontos))
                    tamanho_max = max(w, h)

                    centro_x = x + w // 2
                    centro_y = y + h // 2

                    x = centro_x - tamanho_max // 2
                    y = centro_y - tamanho_max // 2

                    x, y, w, h = x - 10, y - 10, tamanho_max + 20, tamanho_max + 20

                    if self.draw_hand_limits:
                        cv2.rectangle(imagem, (x, y), (x + w, y + h), (64, 71, 238), 2)

                if self.draw_points:
                    mp.solutions.drawing_utils.draw_landmarks(imagem, pontos_mao, self.mp_hands.HAND_CONNECTIONS)
        
        coordenadas = self.ProcessarCoordenadas(lista_pontos, x, y, w, h)

        if 'maos' in locals():
            maos.close()

        return imagem, coordenadas, resultados
    
    def ProcessarCoordenadas(self, lista_pontos, x, y, w, h):
        coordenadas = []
        
        self.a = 0

        for self.a in range(21):
            coordenadas.append([0, 0])
        
        matriz = np.full((100, 100), -1, dtype=int)
        
        if lista_pontos:
            for idx, ponto in enumerate(lista_pontos):
                y_rel = (ponto[1] - y) * 100 // h
                x_rel = (ponto[0] - x) * 100 // w
            
                matriz[y_rel][x_rel] = idx

        for linha in range(matriz.shape[0]):
            for coluna in range(matriz.shape[1]):
                elemento = matriz[coluna, linha]
                if elemento != -1:
                    coordenadas[elemento] = [linha, coluna]

        return coordenadas

    def searchOrder(self, coordenadas):
        pontos_ass = []

        zeros = True

        for idx, ponto in enumerate(coordenadas):
            if [ponto[1], ponto[1]] != [0, 0]:
                zeros = False
            if(idx == 4 or idx == 8 or idx == 12 or idx == 16 or idx == 20):
                pontos_ass.append([ponto[1], ponto[1]])
            
        factor = 25

        ds = []

        for i in range(len(pontos_ass)):
            if i == 4:
                ds.append(self.calcular_distancia(pontos_ass[0], pontos_ass[i]))
            else:
                ds.append(self.calcular_distancia(pontos_ass[i], pontos_ass[i + 1]))

        if not zeros:
            if (ds[0] < factor and ds[1] < factor and ds[2] < factor and ds[3] < factor and ds[4] < factor):
                self.video_record_run = True
                self.video_frame = 1
                self.tempo_anterior = time.time() * 1000
    
    def predict(self, dados):
        dados = (dados).reshape((1, 840))
    
        with open(os.devnull, 'w') as fnull:
            sys.stdout = fnull
            previsoes = self.model.predict(dados)
            sys.stdout = sys.__stdout__

        self.moves = [
            'Fechar Telas',
            'Print screen',
            'Ativar modo mouse virtual',
            'Aumentar o volume',
            'Ir para o canal predileto',
            'Abrir o explorador de arquivos',
            'Diminuir o volume',
            'Aumentar o brilho',
            'Diminuir o brilho',
            'Abrir a netflix',
            'Abrir o disney plus',
            'Confirmar'
        ]

        self.descricoes = [
            'Fechando Telas',
            'Tirando print screen',
            'Ativando modo mouse virtual',
            'Aumentando o volume',
            'Indo para canal predileto',
            'Abrindo o explorador de arquivos',
            'Diminuindo o volume',
            'Aumentando o brilho',
            'Diminuindo o brilho',
            'Abrindo a Netflix',
            'Abrindo Disney Plus',
            'Confirmando'
        ]

        previsoes_tratadas = []
        maior = 0

        for i, previsao in enumerate(previsoes[0]):
            if previsao > previsoes[0][maior]:
                maior = i

            previsoes_tratadas.append(f"{previsao * 100:.2f}%")
        
        previsao = np.argmax(previsoes)
        
        texto = self.descricoes[previsao] + "... - " + str(previsoes_tratadas[previsao])
        self.summary.emit(texto)
        self.last_summary = time.time() * 1000

        if previsao != 2 and previsao != 11:
            
            self.functionExcecute(previsao)
        else:
            self.activateMouseMode()

        previsoes_tratadas = []

    def load_model(self):
        model = load_model('../models/modelTest.keras')

        return model
    
    def drawHand(self, nodes):
        edges = [[0, 1], [1, 2], [2, 3], [3, 4], [0, 5], [5, 6],
                 [6, 7], [7, 8], [0, 17], [5, 9], [9, 13], [13, 17],
                 [9, 10], [10, 11], [11, 12], [13, 14],[14, 15],
                 [15, 16], [17, 18],[18, 19],[19, 20]]
    
        image_mao = nx.DiGraph()
        
        pos = {}
        node_colors = {}

        pos['pa'] = (0, 0)
        pos['pb'] = (100, 100)

        image_mao.add_node('pa')
        image_mao.add_node('pb')

        node_colors['pa'] = "#1e1e2e"
        node_colors['pb'] = "#1e1e2e"

        for i in range(21):
            image_mao.add_node(f'p{i}')

            pos[f'p{i}'] = (nodes[i][0], 100 - (nodes[i][1]))
            node_colors[f'p{i}'] = "#EE4740"
            

        for i in range(21):
            for j in range(21):
                if [i, j] in edges:
                    image_mao.add_edge(f'p{i}', f'p{j}')


        buf = io.BytesIO()
        plt.figure(figsize=(10, 10))
        nx.draw(image_mao, pos, node_size=150, node_color=list(node_colors.values()), edge_color="#EE4740", arrows=False, with_labels=False)
        # nx.draw(image_mao, pos, node_size=150, node_color="#007FFF", edge_color="#003566", arrows=False, with_labels=False)
        plt.savefig(buf, format='png', transparent=True, dpi=300)
        buf.seek(0)
        plt.close()

        qimage = QImage()
        qimage.loadFromData(buf.getvalue())

        self.handImage.emit(qimage)
        
        if 'image_mao' in locals():
            del image_mao
    
    def calcular_distancia(self, ponto1, ponto2):
        return math.sqrt(((ponto2[0] - ponto1[0]) ** 2) + ((ponto2[1] - ponto1[1]) ** 2))
    
    def functionExcecute(self, function):
        function = getattr(self.controler, self.movesAction[function])
        function()

    def activateMouseMode(self):
        self.summary.emit("Entrando no modo mouse...")
        self.change_mouse_sinal.emit(True)
        self.last_summary = time.time() * 1000

        self.mode_mouse = True

    def mouse(self, results):
        if results.multi_hand_landmarks:
            if len(results.multi_hand_landmarks) == 1:
                self.hand_Landmarks = results.multi_hand_landmarks[0]
            self.update_fingers_status()
            self.cursor_moving()
            self.detect_scrolling()
            self.detect_zoomming()
            self.detect_clicking()
            self.detect_dragging()
            self.detect_exit()

    def update_fingers_status(self):
        finger_tips = [20, 8, 12, 16, 4]
        knuckles = [17, 5, 9, 13, 13]

        finger_names = ['little_finger', 'index_finger', 'middle_finger', 'ring_finger', 'Thump_finger']

        for finger_tip, knuckle, finger_name in zip(finger_tips, knuckles, finger_names):
            setattr(self, f'{finger_name}_down', getattr(self.hand_Landmarks.landmark[finger_tip], 'y') > getattr(self.hand_Landmarks.landmark[knuckle], 'y'))
            setattr(self, f'{finger_name}_up', getattr(self.hand_Landmarks.landmark[finger_tip], 'y') < getattr(self.hand_Landmarks.landmark[knuckle], 'y'))

        self.all_fingers_down = self.index_finger_down and self.middle_finger_down and self.ring_finger_down and self.little_finger_down
        self.all_fingers_up = self.index_finger_up and self.middle_finger_up and self.ring_finger_up and self.little_finger_up
        self.index_finger_within_Thumb_finger = self.hand_Landmarks.landmark[8].y > self.hand_Landmarks.landmark[4].y and self.hand_Landmarks.landmark[8].y < self.hand_Landmarks.landmark[2].y
        self.middle_finger_within_Thumb_finger = self.hand_Landmarks.landmark[12].y > self.hand_Landmarks.landmark[4].y and self.hand_Landmarks.landmark[12].y < self.hand_Landmarks.landmark[2].y
        self.little_finger_within_Thumb_finger = self.hand_Landmarks.landmark[20].y > self.hand_Landmarks.landmark[4].y and self.hand_Landmarks.landmark[20].y < self.hand_Landmarks.landmark[2].y
        self.ring_finger_within_Thumb_finger = self.hand_Landmarks.landmark[16].y > self.hand_Landmarks.landmark[4].y and self.hand_Landmarks.landmark[16].y < self.hand_Landmarks.landmark[2].y

    def get_position(self, hand_x_position, hand_y_position):
        old_x, old_y = pyautogui.position()
        current_x = int(hand_x_position * self.screen_width)
        current_y = int(hand_y_position * self.screen_height)

        ratio = 1
        self.prev_hand = (current_x, current_y) if self.prev_hand is None else self.prev_hand
        delta_x = current_x - self.prev_hand[0]
        delta_y = current_y - self.prev_hand[1]
        
        self.prev_hand = [current_x, current_y]
        current_x , current_y = old_x + delta_x * ratio , old_y + delta_y * ratio

        threshold = 5
        if current_x < threshold:
            current_x = threshold
        elif current_x > self.screen_width - threshold:
            current_x = self.screen_width - threshold
        if current_y < threshold:
            current_y = threshold
        elif current_y > self.screen_height - threshold:
            current_y = self.screen_height - threshold

        return (current_x,current_y)
    
    def cursor_moving(self):
        point = 9
        current_x, current_y = self.hand_Landmarks.landmark[point].x ,self.hand_Landmarks.landmark[point].y
        x, y = self.get_position(current_x, current_y)
        cursor_freezed = self.all_fingers_up and self.Thump_finger_down
        if not cursor_freezed:
            pyautogui.moveTo(x, y, duration = 0)

    def detect_scrolling(self):
        scrolling_up =  self.little_finger_up and self.index_finger_down and self.middle_finger_down and self.ring_finger_down
        if scrolling_up:
            pyautogui.scroll(120)
            self.summary.emit("Rolando para cima...")
            self.last_summary = time.time() * 1000

        scrolling_down = self.index_finger_up and self.middle_finger_down and self.ring_finger_down and self.little_finger_down
        if scrolling_down:
            pyautogui.scroll(-120)
            self.summary.emit("Rolando para baixo...")
            self.last_summary = time.time() * 1000

    def detect_zoomming(self):
        zoomming = self.index_finger_up and self.middle_finger_up and self.ring_finger_down and self.little_finger_down
        window = .05
        index_touches_middle = abs(self.hand_Landmarks.landmark[8].x - self.hand_Landmarks.landmark[12].x) <= window
        zoomming_out = zoomming and index_touches_middle
        zoomming_in = zoomming and not index_touches_middle
        
        if zoomming_out:
            pyautogui.keyDown('ctrl')
            pyautogui.scroll(-50)
            pyautogui.keyUp('ctrl')

            self.summary.emit("Diminuindo Zoom...")
            self.last_summary = time.time() * 1000

        if zoomming_in:
            pyautogui.keyDown('ctrl')
            pyautogui.scroll(50)
            pyautogui.keyUp('ctrl')
            self.summary.emit("Aumentando Zoom...")
            self.last_summary = time.time() * 1000

    def detect_clicking(self):
        left_click_condition = self.index_finger_within_Thumb_finger and self.middle_finger_up and self.ring_finger_up and self.little_finger_up and not self.middle_finger_within_Thumb_finger and not self.ring_finger_within_Thumb_finger and not self.little_finger_within_Thumb_finger
        if not self.left_clicked and left_click_condition:
            pyautogui.click()
            self.left_clicked = True
            self.summary.emit("Clicando com o botão esquerdo...")
            self.last_summary = time.time() * 1000
        elif not self.index_finger_within_Thumb_finger:
            self.left_clicked = False

        right_click_condition = self.middle_finger_within_Thumb_finger and self.index_finger_up and self.ring_finger_up and self.little_finger_up and not self.index_finger_within_Thumb_finger and not self.ring_finger_within_Thumb_finger and not self.little_finger_within_Thumb_finger
        if not self.right_clicked and right_click_condition:
            pyautogui.rightClick()
            self.right_clicked = True
            self.summary.emit("Clicando com o botão direito...")
            self.last_summary = time.time() * 1000
        elif not self.middle_finger_within_Thumb_finger:
            self.right_clicked = False

        double_click_condition = self.ring_finger_within_Thumb_finger and self.index_finger_up and self.middle_finger_up and self.little_finger_up and not self.index_finger_within_Thumb_finger and not self.middle_finger_within_Thumb_finger and not self.little_finger_within_Thumb_finger
        if not self.double_clicked and  double_click_condition:
            pyautogui.doubleClick()
            self.double_clicked = True
            self.summary.emit("Clicando duas vezes...")
            self.last_summary = time.time() * 1000
        elif not self.ring_finger_within_Thumb_finger:
            self.double_clicked = False
    
    def detect_dragging(self):
        if not self.dragging and self.all_fingers_down:
            pyautogui.mouseDown(button = "left")
            self.dragging = True
            self.summary.emit("Arrastando...")
            self.last_summary = time.time() * 1000
        elif not self.all_fingers_down:
            pyautogui.mouseUp(button = "left")
            self.dragging = False

    def detect_exit(self):
        if self.little_finger_within_Thumb_finger and self.index_finger_up and self.middle_finger_up and self.ring_finger_up and not self.index_finger_within_Thumb_finger and not self.middle_finger_within_Thumb_finger and not self.ring_finger_within_Thumb_finger:
            self.stopMouseMode()
            
    def stopMouseMode(self):
        self.summary.emit("Saindo do modo mouse...")
        self.change_mouse_sinal.emit(False)
        self.last_summary = time.time() * 1000

        self.mode_mouse = False

        
    
class UI():
    def __init__(self):
        super().__init__()

        self.config_open = False

        self.app = QApplication(sys.argv)
        self.window = QMainWindow()
        self.central_widget = QLabel(self.window)
        self.button = QPushButton("", self.window)
        self.label = QLabel(self.window)
        self.btn1 = QPushButton("Mouse", self.window)
        self.btn2 = QPushButton("Teclado", self.window)
        self.btn3 = QPushButton("Configurações", self.window)
        self.btn4 = QPushButton("Movimentos", self.window)
        self.btn5 = QPushButton("Jogos", self.window)
        self.Texto = QLabel("",self.window)
        self.label2 = QLabel("", self.window)
        self.checkbox = QCheckBox("Exibir pontos", self.window)
        self.checkbox2 = QCheckBox("Exibir limites", self.window)
        self.checkbox3 = QCheckBox("Usar navegação", self.window)
        self.camera_combobox = QComboBox(self.window)
        self.slider = QSlider(QtCore.Qt.Horizontal, self.window)
        self.slider2 = QSlider(QtCore.Qt.Horizontal, self.window)
        self.label3 = QLabel("Entrada de vídeo:", self.window)
        self.label4 = QLabel("Saturação:", self.window)
        self.label5 = QLabel("Brilho:", self.window)

        self.__windowBuild()

    def __windowBuild(self):
        self.window.setWindowTitle("Barium")
        self.window.setGeometry(100, 100, 700, 500)
        self.window.setFixedSize(700, 500)
        self.window.setAttribute(QtCore.Qt.WA_DeleteOnClose)
        self.window.setWindowIcon(QIcon("../img/LOGO.ico"))
        self.window.setStyleSheet("background-color: #1e1e2e;")

        self.central_widget.setPixmap(QPixmap("../img/LogoApp.png").scaled(200, 40))
        self.central_widget.setGeometry(0, 0, 250, 80)
        self.central_widget.setAlignment(QtCore.Qt.AlignCenter)

        self.video_thread = VideoCaptureThread()

        self.button.setGeometry(650, 20, 30, 30)
        self.Texto.setGeometry(20, 395, 200, 25)
        self.btn1.setGeometry(230, 435, 70, 25)
        self.btn2.setGeometry(310, 435, 70, 25)
        self.btn3.setGeometry(390, 435, 110, 25)
        self.btn4.setGeometry(510, 435, 100, 25)
        self.btn5.setGeometry(620, 435, 60, 25)
        self.label.setGeometry(20, 80, 350, 300)
        self.label2.setGeometry(430, 100, 240, 240)

        self.label2.setPixmap(QPixmap("../img/mao.png").scaled(240, 240))

        self.checkbox.setGeometry(450, 80, 0,0)
        self.checkbox2.setGeometry(450, 110, 0,0)
        self.checkbox3.setGeometry(450, 140, 0,0)
        self.label3.setGeometry(450, 180, 0,0)
        self.camera_combobox.setGeometry(450, 210, 0,0)
        self.label4.setGeometry(450, 250, 0,0)
        self.slider.setGeometry(450, 280, 0,0)
        self.label5.setGeometry(450, 310, 0,0)
        self.slider2.setGeometry(450, 340, 0,0)

        self.checkbox.setChecked(self.video_thread.draw_points)
        self.checkbox2.setChecked(self.video_thread.draw_hand_limits)
        self.checkbox3.setChecked(self.video_thread.agir)

        self.populate_camera_combobox()

        self.checkbox.setStyleSheet("color: #CDD6F4; font-size: 14px;")
        self.checkbox2.setStyleSheet("color: #CDD6F4; font-size: 14px;")
        
        self.camera_combobox.setStyleSheet("color: #CDD6F4; font-size: 14px; background-color: #1e1e2e; border: 1px solid #EE4740;")

        self.camera_combobox.view().setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.camera_combobox.view().setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.camera_combobox.view().setStyleSheet("QAbstractItemView {border: 1px solid #EE4740; color: #CDD6F4; font-size: 14px; background-color: #EE4740;}")
        self.camera_combobox.view().setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.camera_combobox.view().setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)

        self.camera_combobox.view().setStyleSheet("QAbstractItemView::item {border: 1px solid #EE4740; color: #CDD6F4; font-size: 14px; background-color: #EE4740;}")
        self.camera_combobox.view().setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.camera_combobox.view().setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)
        
        self.camera_combobox.setCurrentIndex(self.video_thread.cam_indice)

        self.slider.setMinimum(50)
        self.slider.setMaximum(100)
        self.slider.setValue(int(self.video_thread.alpha * 50))
        self.slider.setTickInterval(10)
        self.slider.setTickPosition(QSlider.TicksBelow)

        self.slider2.setMinimum(-50)
        self.slider2.setMaximum(50)
        self.slider2.setValue(self.video_thread.beta)
        self.slider2.setTickInterval(20)
        self.slider2.setTickPosition(QSlider.TicksBelow)

        self.Texto.setStyleSheet("color: #CDD6F4; font-size: 14px;")
        self.label3.setStyleSheet("color: #CDD6F4; font-size: 14px;")
        self.label4.setStyleSheet("color: #CDD6F4; font-size: 14px;")
        self.label5.setStyleSheet("color: #CDD6F4; font-size: 14px;")
        self.button.setStyleSheet("background-color: #077208; border-radius: 15px;")
        self.btn1.setStyleSheet(
            "QPushButton {background-color: #1e1e2e; border: 1px solid #EE4740; border-radius: 10px; color: #EE4740; font-size: 14px;}"
            "QPushButton:hover {background-color: #EE4740; border-radius: 10px; color: #CDD6F4; font-size: 14px;}"
            )
        self.btn2.setStyleSheet(
            "QPushButton {background-color: #1e1e2e; border: 1px solid #EE4740; border-radius: 10px; color: #EE4740; font-size: 14px;}"
            "QPushButton:hover {background-color: #EE4740; border-radius: 10px; color: #CDD6F4; font-size: 14px;}"
            )
        self.btn3.setStyleSheet(
            "QPushButton {background-color: #1e1e2e; border: 1px solid #EE4740; border-radius: 10px; color: #EE4740; font-size: 14px;}"
            "QPushButton:hover {background-color: #EE4740; border-radius: 10px; color: #CDD6F4; font-size: 14px;}"
        )
        self.btn4.setStyleSheet(
            "QPushButton {background-color: #1e1e2e; border: 1px solid #EE4740; border-radius: 10px; color: #EE4740; font-size: 14px;}"
            "QPushButton:hover {background-color: #EE4740; border-radius: 10px; color: #CDD6F4; font-size: 14px;}"
        )
        self.btn5.setStyleSheet(
            "QPushButton {background-color: #1e1e2e; border: 1px solid #EE4740; border-radius: 10px; color: #EE4740; font-size: 14px;}"
            "QPushButton:hover {background-color: #EE4740; border-radius: 10px; color: #CDD6F4; font-size: 14px;}"
        )
        self.checkbox3.setStyleSheet("color: #CDD6F4; font-size: 14px;")
        
        self.label.setStyleSheet("border-radius: 10px; color: #CDD6F4; font-size: 14px; background-color: #1e1e5e;")
        self.label.setAlignment(QtCore.Qt.AlignCenter)
        self.label.setScaledContents(True)
        
        self.label2.setAlignment(QtCore.Qt.AlignCenter)
        self.label2.setScaledContents(True)

        self.button.clicked.connect(self.__on_button_click, QtCore.Qt.UniqueConnection)
        self.btn1.clicked.connect(self.mouse_activate)
        self.btn3.clicked.connect(self.config_alter)
        self.btn4.clicked.connect(self.openMoviments)
        self.btn5.clicked.connect(self.game)
        self.checkbox.stateChanged.connect(self.toggleHandPoints)
        self.checkbox2.stateChanged.connect(self.toggleHandlimits)
        self.checkbox3.stateChanged.connect(self.toggleHandNavigation)
        self.camera_combobox.currentIndexChanged.connect(self.camera_changed)
        self.slider.valueChanged.connect(self.update_alpha)
        self.slider2.valueChanged.connect(self.update_beta)

        self.window.show()
            
        self.video_thread.frameCaptured.connect(self.SetVideo)
        self.video_thread.summary.connect(self.SetText)
        self.video_thread.handImage.connect(self.SetHand)
        self.video_thread.change_mouse_sinal.connect(self.button_change)
        self.video_thread.start()

    def __on_button_click(self):
        self.app.quit()

    def config_alter(self):
        if self.config_alter:
            self.config_alter = False

            self.label2.setGeometry(430, 100, 0, 0)

            self.checkbox.setGeometry(450, 80, 150, 25)
            self.checkbox2.setGeometry(450, 110, 150, 25)
            self.checkbox3.setGeometry(450, 140, 150, 25)
            self.label3.setGeometry(450, 180, 240, 25)
            self.camera_combobox.setGeometry(450, 210, 200, 30)
            self.label4.setGeometry(450, 250, 240, 25)
            self.slider.setGeometry(450, 280, 150, 20)
            self.label5.setGeometry(450, 310, 240, 25)
            self.slider2.setGeometry(450, 340, 150, 20)
        
            self.btn3.setStyleSheet(
                "QPushButton {background-color: #EE4740; border-radius: 10px; color: #CDD6F4; font-size: 14px;}"
                "QPushButton:hover {background-color: #1e1e2e; border: 1px solid #EE4740; border-radius: 10px; color: #EE4740; font-size: 14px;}"
            )

        else:
            self.config_alter = True

            self.label2.setGeometry(430, 100, 240, 240)

            self.checkbox.setGeometry(450, 80, 0,0)
            self.checkbox2.setGeometry(450, 110, 0,0)
            self.checkbox3.setGeometry(450, 140, 0,0)
            self.label3.setGeometry(450, 180, 0,0)
            self.camera_combobox.setGeometry(450, 210, 0,0)
            self.label4.setGeometry(450, 250, 0,0)
            self.slider.setGeometry(450, 280, 0,0)
            self.label5.setGeometry(450, 310, 0,0)
            self.slider2.setGeometry(450, 340, 0,0)

            self.btn3.setStyleSheet(
                "QPushButton {background-color: #1e1e2e; border: 1px solid #EE4740; border-radius: 10px; color: #EE4740; font-size: 14px;}"
                "QPushButton:hover {background-color: #EE4740; border-radius: 10px; color: #CDD6F4; font-size: 14px;}"
            )

    def openMoviments(self):
        webbrowser.open('https://barium-ia.netlify.app/pages/manual.html')

    def SetVideo(self, frame):
        max_width = 380
        self.label.setGeometry(20, 80, max_width, int(frame.height() / (frame.width()/max_width)))
        self.label.setPixmap(QPixmap.fromImage(frame))

    def SetText(self, texto):
        self.Texto.setText(texto)

    def SetHand(self, img):
        if isinstance(img, QImage):
            pixmap = QPixmap.fromImage(img)
            self.label2.setPixmap(pixmap)
        else:
            print("Tipo de imagem não suportado.")

    def toggleHandPoints(self, state):
        self.video_thread.draw_points = state == QtCore.Qt.Checked

        self.video_thread.data['exibicao']['exibir_pontos'] = self.video_thread.draw_points
        with open('config/config.json', 'w') as arquivo:
            json.dump(self.video_thread.data, arquivo, indent=2)

    def toggleHandlimits(self, state):
        self.video_thread.draw_hand_limits = state == QtCore.Qt.Checked

        self.video_thread.data['exibicao']['exibir_limites'] = self.video_thread.draw_hand_limits
        with open('config/config.json', 'w') as arquivo:
            json.dump(self.video_thread.data, arquivo, indent=2)

    def toggleHandNavigation(self, state):
        self.video_thread.agir = state == QtCore.Qt.Checked

        self.video_thread.data['exibicao']['navegar'] = self.video_thread.agir
        with open('config/config.json', 'w') as arquivo:
            json.dump(self.video_thread.data, arquivo, indent=2)

    def camera_changed(self):
        selected_index = self.camera_combobox.currentIndex()
        self.video_thread.cap = cv2.VideoCapture(selected_index)

        self.video_thread.data['video']['entrada'] = selected_index
        with open('config/config.json', 'w') as arquivo:
            json.dump(self.video_thread.data, arquivo, indent=2)

    def update_alpha(self, value):
        self.video_thread.alpha = value / 50

        self.video_thread.data['video']['saturacao'] = self.video_thread.alpha
        with open('config/config.json', 'w') as arquivo:
            json.dump(self.video_thread.data, arquivo, indent=2)

    def update_beta(self, value):
        self.video_thread.beta = value

        self.video_thread.data['video']['brilho'] =  self.video_thread.beta
        with open('config/config.json', 'w') as arquivo:
            json.dump(self.video_thread.data, arquivo, indent=2)

    def populate_camera_combobox(self):
        camera_info = QCameraInfo.availableCameras()

        for info in camera_info:
            self.camera_combobox.addItem(info.description())

    def button_change(self, state):
        if state:
            self.btn1.setStyleSheet(
                "QPushButton {background-color: #EE4740; border-radius: 10px; color: #CDD6F4; font-size: 14px;}"
                "QPushButton:hover {background-color: #1e1e2e; border: 1px solid #EE4740; border-radius: 10px; color: #EE4740; font-size: 14px;}"
            )            
        else:
            self.btn1.setStyleSheet(
                "QPushButton {background-color: #1e1e2e; border: 1px solid #EE4740; border-radius: 10px; color: #EE4740; font-size: 14px;}"
                "QPushButton:hover {background-color: #EE4740; border-radius: 10px; color: #CDD6F4; font-size: 14px;}"
            )

    def mouse_activate(self):
        self.video_thread.change_mouse = True

    def game(self):
        game_script_path = "../modules/games/window.py"
        
        full_path = os.path.join(os.path.dirname(__file__), game_script_path)
        subprocess.Popen(["python", full_path], shell=True)
        sys.exit()


class action():
    def __init__(self):
        pass
    
    def FecharTelas(self):
        pyautogui.hotkey('win', 'd')

    def PrintScreen(self):
        pyautogui.hotkey('win', 'printscreen')

    def AtivarModoMouseVirtual(self):
        pass

    def AumentarVolume(self):
        devices = AudioUtilities.GetSpeakers()
        interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        volume = cast(interface, POINTER(IAudioEndpointVolume))

        current_volume = volume.GetMasterVolumeLevelScalar()
        new_volume = min(1.0, current_volume + 0.1)
        if new_volume > 1.:
            volume.SetMasterVolumeLevelScalar(1., None)
        else:
            volume.SetMasterVolumeLevelScalar(new_volume, None)

    def IrParaCanalPredileto(self):
        webbrowser.open('https://youtube.com')

    def AbrirExploradorDeArquivos(self):
        pyautogui.hotkey('win', 'e')

    def DiminuirVolume(self):
        devices = AudioUtilities.GetSpeakers()
        interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        volume = cast(interface, POINTER(IAudioEndpointVolume))

        current_volume = volume.GetMasterVolumeLevelScalar()
        new_volume = min(1.0, current_volume - 0.1)
        if new_volume < 0:
            volume.SetMasterVolumeLevelScalar(0, None)
        else:
            volume.SetMasterVolumeLevelScalar(new_volume, None)

    def AumentarBrilho(self):
        pass

    def DiminuirBrilho(self):
        pass

    def AbrirNetflix(self):
        webbrowser.open("https://netflix.com")

    def AbrirDisneyPlus(self):
        webbrowser.open("https://disneyplus.com")

    def Confirmar(self):
        pass

def main():
    ui = UI()
    sys.exit(ui.app.exec_())


if __name__ == "__main__":
    main()
#!/usr/bin/env python
# -*- coding: utf-8 -*-


"""
Copyright (C) S. Merkel, Universite de Lille, France

This program is free software; you can redistribute it and/or
modify it under the terms of the GNU General Public License
as published by the Free Software Foundation; either version 2
of the License, or (at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program; if not, write to the Free Software
Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
"""

# System functions, to manipulate command line arguments
import sys
import argparse
from argparse import RawTextHelpFormatter
import os.path

# Fabio, from ESRF fable package
import fabio

# Maths stuff
import numpy
import scipy.misc


# Plotting routines
import matplotlib
matplotlib.use("Qt5Agg")
from matplotlib.figure import Figure
from matplotlib.backend_bases import key_press_handler, Event
from matplotlib.backends.backend_qt5agg import (
    FigureCanvasQTAgg as FigureCanvas,
    NavigationToolbar2QT as NavigationToolbar)


# PyQT graphical interface
import PyQt5.QtWidgets 
import PyQt5.QtCore
import PyQt5.QtGui
import base64


# Some text for the GUI. I put it on top so it is easier to upate
bottomWindowLabel = "(c) 2020, S. Merkel, Univ. Lille"
aboutWindowText = """
<h3>MaskTiff4Maud</h3>
(c) 2020, S. Merkel, Univ. Lille
<P>Utility to prepare tiff files before loading data into the Rietveld refinement software MAUD.
<P>How does this work? MAUD ignores pixels with a -1 intensity. Hence, this software sets a -1 intensity value at all points that should be masked</P>
<P>How to proceed?<ul>
<li>Create a mask, with Dioptas for instance, and save it,</li>
<li>Load you data and your mask in MaskTiff4Maud,</li>
<li>Check that the orientation of the mask is correct, otherwise, flip and rotate the mask until it works,</li>
<li>Save your masked data in Tiff and proceed to process it with MAUD.</li>
</ul>
<P>Good luck with your data!</P>
<P>This program is free software; you can redistribute it and/or modify it under the terms of the GNU General Public License as published by the Free Software Foundation; either version 2 of the License, or (at your option) any later version.</P>
<P>The source code is available at https://github.com/smerkel/maskTiff4Maud.</P>
"""

#################################################################
#
# Simple text window
#
#################################################################

class textWindow(PyQt5.QtWidgets.QDialog):
	def __init__(self, title, content, parent=None):
		super(textWindow, self).__init__(parent)
		
		self.main_frame = PyQt5.QtWidgets.QWidget()
		self.setWindowTitle(title) 

		# Add text field
		self.b = PyQt5.QtWidgets.QTextEdit(self)
		self.b.setHtml(content)
		
		# connect button to function on_click
		button = PyQt5.QtWidgets.QPushButton("Close window", self)
		button.clicked.connect(self.on_click)
		hlay = PyQt5.QtWidgets.QHBoxLayout()
		hlay.addItem(PyQt5.QtWidgets.QSpacerItem(300, 10, PyQt5.QtWidgets.QSizePolicy.Expanding))
		hlay.addWidget(button)
		
		# Vertical box layout in the window and setting it up
		vbox = PyQt5.QtWidgets.QVBoxLayout()
		vbox.addWidget(self.b)
		#self.button.setAlignment(PyQt5.QtCore.Qt.AlignRight | PyQt5.QtCore.Qt.AlignVCenter)
		vbox.addLayout(hlay)
		
		# We are done...
		self.setLayout(vbox)
		self.setGeometry(300, 200, 600, 400)
		self.show()

	def on_click(self):
		self.close()
	
#################################################################
#
# Class to build the Graphical User Interface
#
#################################################################

NavigationToolbar.toolitems = (
	('Home', 'Reset original view', 'home', 'home'), 
	#('Back', 'Previous spectrum', 'back', 'back'), 
	#('Forward', 'Next spectrum', 'forward', 'forward'), 
	#(None, None, None, None), 
	('Pan', 'Pan axes with left mouse, zoom with right', 'move', 'pan'), 
	('Zoom', 'Zoom to rectangle', 'zoom_to_rect', 'zoom'), 
	#(None, None, None, None), 
	('Save', 'Save the figure', 'filesave', 'save_figure'))
	#(None, None, None, None))

class clearMaskGui(PyQt5.QtWidgets.QMainWindow):
	
	"""
	Constructor
	
	Parmeters:
	
	"""
	def __init__(self, parent=None):
		PyQt5.QtWidgets.QMainWindow.__init__(self, parent)
		pm = PyQt5.QtGui.QPixmap()
		pm.loadFromData(base64.b64decode(iconXPMbase64))
		i = PyQt5.QtGui.QIcon()
		i.addPixmap(pm)
		self.setWindowIcon(PyQt5.QtGui.QIcon(i))
		self.mask = None
		self.image = None
		self.plotimagedata = None		# temporary version, used for plotting (reduced resolution)
		self.plotmaskdata = None		# temporary version, used for plotting (reduced resolution and rotated and flipped)
		self.resolution = 1500			# Number of pixels for plotting
		self.intensitycropfactorlow = 1. # for intensity scale in plotting (low intensity side)
		self.intensitycropfactorhigh = 1. # for intensity scale in plotting (high intensity side)
		self.nrotmask = 0     # Number of 90° rotations on mask
		self.intensityshift = 0. # Shift to add to all intensities
		self.flipud = False # Vertical flip on mask
		self.fliplr = False # horizontal flip on mask
		self.donewplot = True # Rescale a clear everything when you will plot
		self.title = "Tiff mask removal tool" # Window title
		self.defaultpath = None # default path with TIFF images
		self.create_main_frame()
		self.on_draw()
		self.show()

	"""
	Builds up the GUI
	"""
	def create_main_frame(self):
		
		# Preparing a frame
		self.main_frame = PyQt5.QtWidgets.QWidget()
		self.setWindowTitle(self.title)
		
		# Building a menu bar
		mainMenu = self.menuBar()
		fileMenu = mainMenu.addMenu('File')
		helpMenu = mainMenu.addMenu('Help')
		
		openButton = PyQt5.QtWidgets.QAction(PyQt5.QtGui.QIcon.fromTheme("document-open"), 'Load Tiff...', self)
		openButton.setShortcut('Ctrl+O')
		openButton.setStatusTip('Load diffraction data...')
		openButton.triggered.connect(self.open_tif)
		fileMenu.addAction(openButton)
		
		openButton = PyQt5.QtWidgets.QAction(PyQt5.QtGui.QIcon.fromTheme("document-open"), 'Load Mask...', self)
		openButton.setStatusTip('Load mask...')
		openButton.triggered.connect(self.open_mask)
		fileMenu.addAction(openButton)
		
		saveButton = PyQt5.QtWidgets.QAction(PyQt5.QtGui.QIcon.fromTheme("document-save-as"), 'Save new Tiff...', self)
		saveButton.setShortcut('Ctrl+S')
		saveButton.setStatusTip('Save new masked data in Tiff...')
		saveButton.triggered.connect(self.save_tif)
		fileMenu.addAction(saveButton)
		
		fileMenu.addSeparator()
		
		exitButton = PyQt5.QtWidgets.QAction(PyQt5.QtGui.QIcon.fromTheme("application-exit"), 'Quit', self)
		exitButton.setShortcut('Ctrl+Q')
		exitButton.setStatusTip('I am done!')
		exitButton.triggered.connect(self.closeEvent)
		fileMenu.addAction(exitButton)
		
		aboutButton = PyQt5.QtWidgets.QAction(PyQt5.QtGui.QIcon.fromTheme("help-about"), 'About this program...', self)
		aboutButton.setShortcut('Ctrl+H')
		aboutButton.setStatusTip('What is this thing?!')
		aboutButton.triggered.connect(self.about)
		helpMenu.addAction(aboutButton)


		# Horizontal
		#hlay = PyQt5.QtWidgets.QHBoxLayout()
		#button = PyQt5.QtWidgets.QPushButton(PyQt5.QtGui.QIcon.fromTheme("document-open"), 'Load data', self)
		#button.setToolTip('Load diffraction data...')
		#button.clicked.connect(self.open_tif)
		#hlay.addWidget(button)
		#button = PyQt5.QtWidgets.QPushButton(PyQt5.QtGui.QIcon.fromTheme("document-save"), 'Save data', self)
		#button.setToolTip('Save diffraction data...')
		#button.clicked.connect(self.save_tif)
		#hlay.addWidget(button)
		#hlay.addStretch(1)

		
		# Vertical layout with all options
		cropLabel1 = PyQt5.QtWidgets.QLabel("Color shift (low intensities)", self)
		self.colorScalingLow = PyQt5.QtWidgets.QSlider(PyQt5.QtCore.Qt.Horizontal)
		self.colorScalingLow.setMinimum(-20)
		self.colorScalingLow.setMaximum(20)
		self.colorScalingLow.setSingleStep(1)
		self.colorScalingLow.setValue(numpy.log(self.intensitycropfactorlow))
		self.colorScalingLow.setTickPosition(PyQt5.QtWidgets.QSlider.NoTicks)
		self.colorScalingLow.valueChanged.connect(self.changeColorScaleValue)
		
		cropLabel2 = PyQt5.QtWidgets.QLabel("Color shift (high intensities)", self)
		self.colorScalingHigh = PyQt5.QtWidgets.QSlider(PyQt5.QtCore.Qt.Horizontal)
		self.colorScalingHigh.setMinimum(-20)
		self.colorScalingHigh.setMaximum(20)
		self.colorScalingHigh.setSingleStep(1)
		self.colorScalingHigh.setValue(numpy.log(self.intensitycropfactorhigh))
		self.colorScalingHigh.setTickPosition(PyQt5.QtWidgets.QSlider.NoTicks)
		self.colorScalingHigh.valueChanged.connect(self.changeColorScaleValue)
		
		intLabel = PyQt5.QtWidgets.QLabel("Intensity shift on data", self)
		self.intShiftBox = PyQt5.QtWidgets.QLineEdit("%.1f" % (self.intensityshift ), self)
		self.intShiftBox.returnPressed.connect(self.changeIntensityShiftValue)
		
		rotLabel = PyQt5.QtWidgets.QLabel("N. 90° rotation on mask", self)
		self.rotBox = PyQt5.QtWidgets.QLineEdit("%d" % (self.nrotmask), self)
		self.rotBox.returnPressed.connect(self.change_mask)
		self.flipV = PyQt5.QtWidgets.QCheckBox("Flip mask vertically",self)
		self.flipV.stateChanged.connect(self.change_mask)
		self.flipH = PyQt5.QtWidgets.QCheckBox("Flip mask horizontally",self)
		self.flipH.stateChanged.connect(self.change_mask)

		resLabel = PyQt5.QtWidgets.QLabel("Plot resolution (pixels)", self)
		self.resBox = PyQt5.QtWidgets.QLineEdit("%d" % (self.resolution), self)
		self.resBox.setValidator(PyQt5.QtGui.QIntValidator(0,10000))
		self.resBox.returnPressed.connect(self.changeResolutionValue)

		vlay = PyQt5.QtWidgets.QVBoxLayout()
		vlay.addWidget(cropLabel1)
		vlay.addWidget(self.colorScalingLow)
		vlay.addWidget(cropLabel2)
		vlay.addWidget(self.colorScalingHigh)
		vlay.addWidget(intLabel)
		vlay.addWidget(self.intShiftBox)
		vlay.addWidget(rotLabel)
		vlay.addWidget(self.rotBox)
		vlay.addWidget(self.flipV)
		vlay.addWidget(self.flipH)
		label = PyQt5.QtWidgets.QLabel("Data file", self)
		vlay.addWidget(label)
		self.dataBox = PyQt5.QtWidgets.QLineEdit("Not set", self)
		self.dataBox.setReadOnly(True)
		palette = PyQt5.QtGui.QPalette()
		palette.setColor(PyQt5.QtGui.QPalette.Text, PyQt5.QtCore.Qt.lightGray)
		self.dataBox.setPalette(palette)
		self.dataBox.setStyleSheet('font:italic;')
		vlay.addWidget(self.dataBox)
		label = PyQt5.QtWidgets.QLabel("Mask file", self)
		vlay.addWidget(label)
		self.maskBox = PyQt5.QtWidgets.QLineEdit("Not set", self)
		self.maskBox.setReadOnly(True)
		self.maskBox.setPalette(palette)
		self.maskBox.setStyleSheet('font:italic;')
		vlay.addWidget(self.maskBox)
		vlay.addWidget(resLabel)
		vlay.addWidget(self.resBox)
		vlay.addItem(PyQt5.QtWidgets.QSpacerItem(10, 200, PyQt5.QtWidgets.QSizePolicy.Expanding))
		
		# Adding a canvas for the plot
		self.fig = Figure((8.0, 8.0), dpi=100,tight_layout=True,edgecolor='w',facecolor='w')
		self.canvas = FigureCanvas(self.fig)
		self.canvas.setParent(self.main_frame)
		self.canvas.setFocusPolicy(PyQt5.QtCore.Qt.StrongFocus)
		self.canvas.setFocus()

		# Adding a toolbar and trying to deal with the events
		self.mpl_toolbar = NavigationToolbar(self.canvas, self.main_frame)

		# Horizontal box at the center, with the options and the plot
		hlay2 = PyQt5.QtWidgets.QHBoxLayout()
		hlay2.addLayout(vlay)
		hlay2.addWidget(self.canvas)  # the matplotlib canvas

		# Vertical box layout in the window and setting it up
		vbox = PyQt5.QtWidgets.QVBoxLayout()
		#vbox.addLayout(hlay)
		vbox.addLayout(hlay2)
		vbox.addWidget(self.mpl_toolbar)
		
		# Adding labels at the bottom
		windowLabel = PyQt5.QtWidgets.QLabel(bottomWindowLabel, self)
		windowLabel.setAlignment(PyQt5.QtCore.Qt.AlignRight | PyQt5.QtCore.Qt.AlignVCenter)
		vbox.addWidget(windowLabel)

		# We are done...
		self.main_frame.setLayout(vbox)
		self.setCentralWidget(self.main_frame)
	
	"""
	Draws or redraws the plot
	"""
	def on_draw(self):
		# If not instructed to do a new plot, keep a memory of the zoom
		if (not self.donewplot):
			# Clear plot content
			for artist in self.axes.get_images():
				artist.remove()
		else:
			# Clear plot
			self.fig.clear()
			rect = 0, 0, 1., 1.
			self.axes = self.fig.add_axes(rect)
			self.axes.tick_params(axis='both', labelbottom=False, labeltop=False, labelleft=False, labelright=False)
		if (self.image != None):
			median = numpy.median(self.plotimagedata) + self.intensityshift
			mindata = self.plotimagedata.min() + self.intensityshift
			maxdata = self.plotimagedata.max() + self.intensityshift
			minI = median-(median-mindata)*0.1*self.intensitycropfactorlow
			maxI = median+(maxdata-median)*0.1*self.intensitycropfactorhigh
			self.axes.imshow(self.plotimagedata + self.intensityshift,cmap = 'gnuplot2', vmin=minI, vmax=maxI)
			self.donewplot = False
		if (self.mask != None):
			self.axes.imshow(self.plotmaskdata, origin='lower', cmap='OrRd', alpha=0.2)
		self.canvas.draw()
	
	"""
	Deals with changes in mask flipping and rotation options
	"""
	def change_mask(self,evt=None):
		self.fliplr = False
		self.flipud = False
		if (self.flipV.checkState() == PyQt5.QtCore.Qt.Checked):
			self.flipud = True
		if (self.flipH.checkState() == PyQt5.QtCore.Qt.Checked):
			self.fliplr = True
		self.nrotmask = int(self.rotBox.text())
		if (self.mask != None):
			maskdata = self.mask.data
			if (self.nrotmask > 0):
				maskdata = numpy.rot90(maskdata,self.nrotmask)
			if (self.flipud):
				maskdata = numpy.flipud(maskdata)
			if (self.fliplr):
				maskdata = numpy.fliplr(maskdata)
			# Generating reduced resolution version for plotting
			ratio = 1.0* self.resolution / max(self.mask.dim1,self.mask.dim2)
			self.plotmaskdata =  scipy.misc.imresize(maskdata,ratio)
			self.on_draw()
	
	"""
	Deals with changes in input boxes for intensity shift
	"""
	def changeIntensityShiftValue(self,evt=None):
		self.intensityshift = float(self.intShiftBox.text())
		self.checkForNegativeValues()
		self.on_draw()

	"""
	Deals with changes in color scale
	"""
	def changeColorScaleValue(self,evt=None):
		self.intensitycropfactorlow = numpy.power(10.,self.colorScalingLow.value()/10.)
		self.intensitycropfactorhigh = numpy.power(10.,self.colorScalingHigh.value()/10.)
		self.on_draw()
		
	"""
	Deals with changes in plot resolution
	"""
	def changeResolutionValue(self,evt=None):
		self.resolution = int(self.resBox.text())
		if (self.image != None):
			ratio = 1.0* self.resolution / max(self.image.dim1,self.image.dim2)
			self.plotimagedata =  scipy.misc.imresize(self.image.data,ratio)
		if (self.mask != None):
			ratio = 1.0* self.resolution / max(self.mask.dim1,self.mask.dim2)
			self.plotmaskdata =  scipy.misc.imresize(self.mask.data,ratio)
		self.on_draw()
		
	"""
	Open the diffraction image file
	"""
	def open_tif(self,evt=None):
		options = PyQt5.QtWidgets.QFileDialog.Options()
		filename, _ = PyQt5.QtWidgets.QFileDialog.getOpenFileName(self,"Select an tiff file...", self.defaultpath,"Tiff Files (*.tif *.tiff);;All Files (*)", options=options)
		if filename:
			self.image = fabio.open(filename)
			path, name = os.path.split(filename)
			self.imagefilename = name
			self.defaultpath = path
			self.title = "Tiff mask removal tool: %s" % name
			self.setWindowTitle(self.title)
			self.dataBox.setText(name)
			self.checkForNegativeValues()
			# Generating reduced resolution version for plotting
			ratio = 1.0* self.resolution / max(self.image.dim1,self.image.dim2)
			self.plotimagedata =  scipy.misc.imresize(self.image.data,ratio)
			self.donewplot = True
			self.on_draw()
	
	"""
	Open the mask file
	"""
	def open_mask(self,evt=None):
		options = PyQt5.QtWidgets.QFileDialog.Options()
		filename, _ = PyQt5.QtWidgets.QFileDialog.getOpenFileName(self,"Select your mask...", self.defaultpath,"Mask Files (*.mask);;All Files (*)", options=options)
		if filename:
			self.mask = fabio.open(filename)
			path, name = os.path.split(filename)
			# self.title = "MAUD ESG edit: " + name
			self.maskfilename = name
			self.maskBox.setText(name)
			self.checkForNegativeValues()
			# Generating reduced resolution version for plotting
			ratio = 1.0* self.resolution / max(self.mask.dim1,self.mask.dim2)
			self.plotmaskdata =  scipy.misc.imresize(self.mask.data,ratio)
			self.on_draw()

	"""
	Check if there are negative intensities where there is no mask
	This is a problem later in MAUD
	"""
	def checkForNegativeValues(self):
		if ((self.mask == None) or (self.image == None)):
			return False
		thisdata = self.image.data + self.intensityshift
		maskdata = self.mask.data
		if (self.nrotmask > 0):
			maskdata = numpy.rot90(maskdata,self.nrotmask)
		if (self.flipud):
			maskdata = numpy.flipud(maskdata)
		if (self.fliplr):
			maskdata = numpy.fliplr(maskdata)
		idx=(maskdata != 1)
		minval = min(thisdata[idx])
		if (minval < 0):
			recommended = self.intensityshift - minval
			buttonReply = PyQt5.QtWidgets.QMessageBox.warning(self, 'Negative intensities', "Negative intensites in un-masked data. Minimum intensity shift to avoid this: %.1f" % recommended, PyQt5.QtWidgets.QMessageBox.Ok)
			
	"""
	Returns the data after all corrections
	"""
	def correctedData(self):
		if ((self.mask == None) or (self.image == None)):
			return False
		thisdata = self.image.data + self.intensityshift
		maskdata = self.mask.data 
		maskdata = numpy.rot90(maskdata,self.nrotmask)
		if (self.flipud):
			maskdata = numpy.flipud(maskdata)
		if (self.fliplr):
			maskdata = numpy.fliplr(maskdata)
		idx=(maskdata == 1)
		thisdata[idx]=-1
		return thisdata
	
	
	"""
	Save the new image with the mask remove
	"""
	def save_tif(self,evt=None):
		if ((self.mask == None) or (self.image == None)):
			buttonReply = PyQt5.QtWidgets.QMessageBox.warning(self, 'No data', "Data or mask is missing. Nothing to save.", PyQt5.QtWidgets.QMessageBox.Ok)
			return
		options = PyQt5.QtWidgets.QFileDialog.Options()
		fileName, _ = PyQt5.QtWidgets.QFileDialog.getSaveFileName(self,"Save new data as...", self.defaultpath,"Tiff Files (*.tif *.tiff);;All Files (*)", options=options)
		if fileName:
			# Saving into a new file
			imtiff = fabio.tifimage.tifimage(self.correctedData())
			imtiff.write(fileName)
			path, name = os.path.split(fileName)
			self.defaultpath = path
			self.title = "Tiff mask removal tool: %s" % name
			self.setWindowTitle(self.title)
		return

	"""
	Called when the window is closed or when the user decides to "Quit"
	"""
	def closeEvent(self,evt=None):
		if (isinstance(evt,PyQt5.QtGui.QCloseEvent)):
			evt.accept()
		sys.exit(2)
	
	"""
	About window
	"""
	def about(self,evt=None):
		dialog = textWindow("About maskTiff4Maud...", aboutWindowText, self)
		dialog.exec_()
		return

#################################################################
#
# Application icon in XPM format, encoded in base64
#
#################################################################

iconXPMbase64 = "LyogWFBNICovCnN0YXRpYyBjaGFyICogbWFza1RpZmY0TWF1ZF94cG1bXSA9IHsKIjg4IDgyIDE5ODggMiIsCiIgIAljIE5vbmUiLAoiLiAJYyAjMDAwMENGIiwKIisgCWMgIzAwMDBDRSIsCiJAIAljICMxQTFBRDMiLAoiIyAJYyAjNUM1Q0RGIiwKIiQgCWMgI0EzQTNFRSIsCiIlIAljICNDNkM2RjQiLAoiJiAJYyAjRTRFNEY5IiwKIiogCWMgI0U3RTdGQiIsCiI9IAljICNDRUNFRjUiLAoiLSAJYyAjQUVBRUVGIiwKIjsgCWMgIzZFNkVFMyIsCiI+IAljICMyOTI5RDYiLAoiLCAJYyAjMDEwMUNFIiwKIicgCWMgIzAwMDBDRCIsCiIpIAljICMxRDFERDQiLAoiISAJYyAjOTk5OUVDIiwKIn4gCWMgI0ZGRkZGRiIsCiJ7IAljICNCQ0JDRjMiLAoiXSAJYyAjMzIzMkQ4IiwKIl4gCWMgIzU0NTRERSIsCiIvIAljICNGOUY5RkUiLAoiKCAJYyAjODI4MkU3IiwKIl8gCWMgIzA0MDRDRiIsCiI6IAljICM3Nzc3RTUiLAoiPCAJYyAjQUNBQ0VGIiwKIlsgCWMgIzA3MDdDRiIsCiJ9IAljICM1QTVBREYiLAoifCAJYyAjOTU5NUVBIiwKIjEgCWMgIzI3MjdENSIsCiIyIAljICNGQkZCRkUiLAoiMyAJYyAjQUFBQUVGIiwKIjQgCWMgI0ZGRkVGRSIsCiI1IAljICNGRUZCRkIiLAoiNiAJYyAjRjhGNEY0IiwKIjcgCWMgI0YxRUZFRCIsCiI4IAljICNFOUU5RTYiLAoiOSAJYyAjRTRFNkUzIiwKIjAgCWMgI0UxRTVFMCIsCiJhIAljICNERUUxREIiLAoiYiAJYyAjRDlEREQ3IiwKImMgCWMgI0Q3RDlENSIsCiJkIAljICNENkQ4RDQiLAoiZSAJYyAjRDdEOUQ2IiwKImYgCWMgI0RBREJEOCIsCiJnIAljICNERURGREUiLAoiaCAJYyAjRTJFMkUxIiwKImkgCWMgI0U2RTRFMyIsCiJqIAljICNFRkVCRUEiLAoiayAJYyAjRjdGMEYwIiwKImwgCWMgI0ZDRjVGNyIsCiJtIAljICNGQ0ZBRkEiLAoibiAJYyAjRkVGRUZFIiwKIm8gCWMgI0UyRTJGOSIsCiJwIAljICMwQTBBRDAiLAoicSAJYyAjMkIyQkQ2IiwKInIgCWMgI0ZFRkNGQyIsCiJzIAljICNGNEVFRUUiLAoidCAJYyAjRUFEQ0RDIiwKInUgCWMgI0UxQ0ZEMCIsCiJ2IAljICNEMkMxQkYiLAoidyAJYyAjQkVCNkIzIiwKInggCWMgI0JCQkRCMyIsCiJ5IAljICNCQ0M1QjciLAoieiAJYyAjQkFDOEI2IiwKIkEgCWMgI0JEQ0NCOSIsCiJCIAljICNCQUM3QjYiLAoiQyAJYyAjQjZDM0IyIiwKIkQgCWMgI0I0QkZCMSIsCiJFIAljICNCMkJDQjAiLAoiRiAJYyAjQjBCN0FFIiwKIkcgCWMgI0FGQjRBRSIsCiJIIAljICNCMUIzQUYiLAoiSSAJYyAjQjRCMEFEIiwKIkogCWMgI0JGQjFCMCIsCiJLIAljICNENUI4QjkiLAoiTCAJYyAjRTNDNEM2IiwKIk0gCWMgI0U2RDBEMCIsCiJOIAljICNFRkUxRTEiLAoiTyAJYyAjRjZFREVEIiwKIlAgCWMgI0Y5RjJGMyIsCiJRIAljICM1RDVERTAiLAoiUiAJYyAjNzE3MUU0IiwKIlMgCWMgI0Y2RjVGNSIsCiJUIAljICNFNUUwRTAiLAoiVSAJYyAjRERDRkQwIiwKIlYgCWMgI0Q5QzBDMyIsCiJXIAljICNENEI1QjgiLAoiWCAJYyAjRDRCMUIyIiwKIlkgCWMgI0QyQUVBRSIsCiJaIAljICNDOEFEQUMiLAoiYCAJYyAjQjZBQkFCIiwKIiAuCWMgI0I1QjVCMCIsCiIuLgljICNCREM2QjkiLAoiKy4JYyAjQkZDRUJCIiwKIkAuCWMgI0MzRDJCQyIsCiIjLgljICNDMUNFQjkiLAoiJC4JYyAjQkRDQUI3IiwKIiUuCWMgI0JBQzdCNyIsCiImLgljICNCOEMyQjUiLAoiKi4JYyAjQjRCQUIyIiwKIj0uCWMgI0FGQUZBRCIsCiItLgljICNCMEFDQUIiLAoiOy4JYyAjQkNBQkFCIiwKIj4uCWMgI0QzQURBRSIsCiIsLgljICNFMEFEQUUiLAoiJy4JYyAjRTFCMEFGIiwKIikuCWMgI0UxQjRCMyIsCiIhLgljICNFMkJCQkEiLAoifi4JYyAjRUVEMUQwIiwKInsuCWMgI0YxRTBERSIsCiJdLgljICNGQUYzRjIiLAoiXi4JYyAjQjNCM0YwIiwKIi8uCWMgI0MyQzJGNCIsCiIoLgljICNFREU3RTciLAoiXy4JYyAjRTRENkQ2IiwKIjouCWMgI0QzQjhCOSIsCiI8LgljICNEMkIwQjEiLAoiWy4JYyAjRDVBQ0FFIiwKIn0uCWMgI0Q4QUJBRCIsCiJ8LgljICNEOUFCQUMiLAoiMS4JYyAjREFBQkFCIiwKIjIuCWMgI0Q2QURBRCIsCiIzLgljICNDQkFEQUQiLAoiNC4JYyAjQkZBQ0FCIiwKIjUuCWMgI0I4QUNBQiIsCiI2LgljICNCNkIxQUIiLAoiNy4JYyAjQjdCNEFDIiwKIjguCWMgI0I4QjVBQyIsCiI5LgljICNCNUIyQUIiLAoiMC4JYyAjQjNBRkFCIiwKImEuCWMgI0I0QURBQiIsCiJiLgljICNCN0FDQUIiLAoiYy4JYyAjQkFBQkFCIiwKImQuCWMgI0MwQUJBQiIsCiJlLgljICNDN0FEQUQiLAoiZi4JYyAjRDVBREFEIiwKImcuCWMgI0UzQURBRSIsCiJoLgljICNFOUFDQUMiLAoiaS4JYyAjRUFBQ0FCIiwKImouCWMgI0U5QUNBQiIsCiJrLgljICNFN0FEQUQiLAoibC4JYyAjRTNBRkFFIiwKIm0uCWMgI0UyQjhCNiIsCiJuLgljICNFQUM5QzciLAoiby4JYyAjRjZFMkUwIiwKInAuCWMgI0ZCRjRGNCIsCiJxLgljICNGQ0ZDRkYiLAoici4JYyAjMEIwQkQwIiwKInMuCWMgI0VFRUVGQyIsCiJ0LgljICM2NzY3QzciLAoidS4JYyAjMDcwN0E0IiwKInYuCWMgIzAwMDBBMSIsCiJ3LgljICMwODA2QTEiLAoieC4JYyAjNjI0REE1IiwKInkuCWMgI0RDQUJBQiIsCiJ6LgljICNEREFCQUMiLAoiQS4JYyAjREZBQkFDIiwKIkIuCWMgI0QxQTJBQyIsCiJDLgljICMzNDI5QTMiLAoiRC4JYyAjMTAwREEyIiwKIkUuCWMgIzMyMjRBMyIsCiJGLgljICNFNEE0QUIiLAoiRy4JYyAjRUVBQkFDIiwKIkguCWMgI0VEQUNBQyIsCiJJLgljICNFQkFEQUUiLAoiSi4JYyAjRTZCNUI2IiwKIksuCWMgIzQyM0FBRCIsCiJMLgljICMwMTAxQTEiLAoiTS4JYyAjMDkwOUE0IiwKIk4uCWMgIzg0ODREMiIsCiJPLgljICMyMjIyRDQiLAoiUC4JYyAjMDkwOUNGIiwKIlEuCWMgIzExMTFBNyIsCiJSLgljICMwNzA1QTEiLAoiUy4JYyAjREFBQ0FCIiwKIlQuCWMgI0RDQUNBQiIsCiJVLgljICNFMUFCQUMiLAoiVi4JYyAjQjM4OEFBIiwKIlcuCWMgI0I1ODFBQSIsCiJYLgljICNGMUFCQUMiLAoiWS4JYyAjRjJBQkFDIiwKIlouCWMgI0YxQUNBQyIsCiJgLgljICNEQTlFQUIiLAoiICsJYyAjMjkyOUIwIiwKIi4rCWMgIzM3MzdEOCIsCiIrKwljICMwRjBGRDEiLAoiQCsJYyAjMDQwNEEyIiwKIiMrCWMgIzIyMjJBRSIsCiIkKwljICMwRjBGQTciLAoiJSsJYyAjMjkyNkE5IiwKIiYrCWMgIzI5MjNBNiIsCiIqKwljICMyOTIxQTQiLAoiPSsJYyAjMjkyMEEzIiwKIi0rCWMgIzJBMjBBMyIsCiI7KwljICMwNjA1QTIiLAoiPisJYyAjRDhBOUFCIiwKIiwrCWMgI0RDQUNBQyIsCiInKwljICNERUFCQUIiLAoiKSsJYyAjRTBBQkFCIiwKIiErCWMgI0UyQUJBQiIsCiJ+KwljICNEREE3QUIiLAoieysJYyAjNjM0QkE1IiwKIl0rCWMgIzNEMkVBNCIsCiJeKwljICMyQjIwQTMiLAoiLysJYyAjMTQwRkEyIiwKIigrCWMgIzEzMEVBMiIsCiJfKwljICMyQzIwQTMiLAoiOisJYyAjMkQyMEEzIiwKIjwrCWMgIzNFMkNBNCIsCiJbKwljICM2NDQ3QTUiLAoifSsJYyAjRTdBNUFEIiwKInwrCWMgI0YyQUNBRCIsCiIxKwljICNGM0FDQUMiLAoiMisJYyAjRjRBQ0FDIiwKIjMrCWMgIzc1NTVBNyIsCiI0KwljICMyRDI1QTUiLAoiNSsJYyAjMjUyMkE1IiwKIjYrCWMgIzBGMEZBNiIsCiI3KwljICMxMjEyQTciLAoiOCsJYyAjMDIwMkEyIiwKIjkrCWMgIzIwMjBBQyIsCiIwKwljICMzRjNGREEiLAoiYSsJYyAjMDEwMUEyIiwKImIrCWMgIzFBMUFBQiIsCiJjKwljICM1RjVGQzQiLAoiZCsJYyAjNjI1OUIzIiwKImUrCWMgI0Q3QjJCMyIsCiJmKwljICNEQ0FEQUUiLAoiZysJYyAjREVBQ0FCIiwKImgrCWMgI0RGQUNBQiIsCiJpKwljICMyODFGQTMiLAoiaisJYyAjRDRBM0FDIiwKImsrCWMgI0UxQUJBQiIsCiJsKwljICNFM0FCQUIiLAoibSsJYyAjRTRBQkFCIiwKIm4rCWMgI0U0QUJBQyIsCiJvKwljICNFNUFDQUMiLAoicCsJYyAjRTVBQkFCIiwKInErCWMgI0U2QUJBQiIsCiJyKwljICNFN0FCQUIiLAoicysJYyAjRThBQkFCIiwKInQrCWMgIzZFNTBBNiIsCiJ1KwljICM2QjRFQTYiLAoidisJYyAjRURBQkFDIiwKIncrCWMgI0VDQUNBQiIsCiJ4KwljICNFRUFDQUIiLAoieSsJYyAjRjFBQ0FCIiwKInorCWMgI0YyQUNBQyIsCiJBKwljICNGMkFEQUMiLAoiQisJYyAjRjJBREFEIiwKIkMrCWMgI0YzQUVBRCIsCiJEKwljICNGNUFFQUUiLAoiRSsJYyAjRjZBRUFGIiwKIkYrCWMgI0Y2QURBRiIsCiJHKwljICNGN0FEQUQiLAoiSCsJYyAjRjRBRUFDIiwKIkkrCWMgI0U2QUZBRSIsCiJKKwljICNCRkFDQUMiLAoiSysJYyAjNDU0NUE3IiwKIkwrCWMgIzZGNkZDQSIsCiJNKwljICMwQjBCQTUiLAoiTisJYyAjRjhGOEZDIiwKIk8rCWMgIzIxMjFBRCIsCiJQKwljICM2MDYwQzMiLAoiUSsJYyAjNjM1MEE5IiwKIlIrCWMgI0RFQUNBRSIsCiJTKwljICNFMEFDQUIiLAoiVCsJYyAjMzAyNUEzIiwKIlUrCWMgI0NFOUVBQyIsCiJWKwljICNFNUFCQUMiLAoiVysJYyAjRTZBQkFDIiwKIlgrCWMgI0U4QUNBQiIsCiJZKwljICNFOUFCQUIiLAoiWisJYyAjNkU1MEE1IiwKImArCWMgIzZDNEVBNiIsCiIgQAljICNFRkFDQUMiLAoiLkAJYyAjRjFBREFDIiwKIitACWMgI0YzQUVBQyIsCiJAQAljICNGNEFGQUQiLAoiI0AJYyAjRjZBRkFFIiwKIiRACWMgI0Y4QUZBRiIsCiIlQAljICNGOUFGQjAiLAoiJkAJYyAjRkFCMEIyIiwKIipACWMgI0ZBQjBCMCIsCiI9QAljICNGOEIwQUUiLAoiLUAJYyAjRjFCMUIwIiwKIjtACWMgI0M1QURBRCIsCiI+QAljICM0NDQzQTUiLAoiLEAJYyAjNzA3MEM1IiwKIidACWMgI0VDRUNGOCIsCiIpQAljICMyNzI3QUYiLAoiIUAJYyAjNjk2NUJFIiwKIn5ACWMgIzY2NEVBNyIsCiJ7QAljICNFMkFDQUMiLAoiXUAJYyAjMzkyQ0E0IiwKIl5ACWMgI0M4OThBQSIsCiIvQAljICNFMUFDQUIiLAoiKEAJYyAjRTdBQkFDIiwKIl9ACWMgI0VBQUJBQyIsCiI6QAljICM2RjUwQTYiLAoiPEAJYyAjRUZBQkFDIiwKIltACWMgI0VGQUNBRCIsCiJ9QAljICNGMEFDQUUiLAoifEAJYyAjRjJBREFFIiwKIjFACWMgI0Y0QUVBRSIsCiIyQAljICNGNUFGQUYiLAoiM0AJYyAjRjdCMUIwIiwKIjRACWMgI0ZBQjFCMSIsCiI1QAljICNGQkIyQjIiLAoiNkAJYyAjRkRCM0I0IiwKIjdACWMgI0ZEQjRCNCIsCiI4QAljICNGN0I0QjUiLAoiOUAJYyAjQ0NBRkFFIiwKIjBACWMgIzQ1NDRBNSIsCiJhQAljICM2NTY1QjEiLAoiYkAJYyAjRjFFRkVGIiwKImNACWMgI0UxRTFGNCIsCiJkQAljICMyRTJFQjIiLAoiZUAJYyAjRkNGQ0ZDIiwKImZACWMgI0U2RENEQyIsCiJnQAljICM2ODVCQUYiLAoiaEAJYyAjNjc0RUE2IiwKImlACWMgI0UyQUNBQiIsCiJqQAljICM0MjMyQTQiLAoia0AJYyAjQzE5NEFCIiwKImxACWMgI0UzQUJBQyIsCiJtQAljICNFNkFDQUMiLAoibkAJYyAjRTVBQ0FCIiwKIm9ACWMgI0U4QUJBQyIsCiJwQAljICNFOUFCQUMiLAoicUAJYyAjRUJBQkFCIiwKInJACWMgIzZGNTBBNSIsCiJzQAljICNGMEFEQUQiLAoidEAJYyAjRjFBREFFIiwKInVACWMgI0YzQUVBRiIsCiJ2QAljICNGN0IxQjEiLAoid0AJYyAjRjlCM0IyIiwKInhACWMgI0ZDQjRCNCIsCiJ5QAljICNGREI2QjUiLAoiekAJYyAjRkZCN0I3IiwKIkFACWMgI0ZGQjhCOCIsCiJCQAljICNGRkI5QjgiLAoiQ0AJYyAjRkFCOUJBIiwKIkRACWMgI0Q1QjVCNSIsCiJFQAljICM0NzQ1QTciLAoiRkAJYyAjNUM1Q0E3IiwKIkdACWMgI0MyQzJDMSIsCiJIQAljICNFRUVFRUUiLAoiSUAJYyAjRkNGQ0ZFIiwKIkpACWMgIzc3NzdDRCIsCiJLQAljICNBNkE2REUiLAoiTEAJYyAjMTgxOEFBIiwKIk1ACWMgIzI0MjRBRiIsCiJOQAljICNENkQ2RjAiLAoiT0AJYyAjMzQzNEI0IiwKIlBACWMgI0VBRTJFMyIsCiJRQAljICNEREJFQkYiLAoiUkAJYyAjNjk1MkE2IiwKIlNACWMgIzY4NEVBNiIsCiJUQAljICNFNUFCQUQiLAoiVUAJYyAjNEIzOEE0IiwKIlZACWMgI0JBOERBQSIsCiJXQAljICNFNEFCQUQiLAoiWEAJYyAjRTRBQ0FDIiwKIllACWMgI0U2QUNBQiIsCiJaQAljICNFQkFCQUMiLAoiYEAJYyAjRUNBQkFCIiwKIiAjCWMgI0YyQUVBRiIsCiIuIwljICNGNUFGQjAiLAoiKyMJYyAjRkNCNUI0IiwKIkAjCWMgI0ZEQjdCNyIsCiIjIwljICNGRUI5QjkiLAoiJCMJYyAjRkZCQkJCIiwKIiUjCWMgI0ZGQkNCQyIsCiImIwljICNGRkJFQkUiLAoiKiMJYyAjRkZCRUJGIiwKIj0jCWMgI0ZDQkZDMCIsCiItIwljICNFMUJGQkYiLAoiOyMJYyAjNEE0N0E5IiwKIj4jCWMgIzVENUNBNyIsCiIsIwljICNBQkFDQUIiLAoiJyMJYyAjQzBDMUMxIiwKIikjCWMgI0ZBRkFGQSIsCiIhIwljICNCOEI4RTUiLAoifiMJYyAjNkE2QUM4IiwKInsjCWMgIzE5MTlBQSIsCiJdIwljICM4NTg1RDIiLAoiXiMJYyAjQ0JDQkVCIiwKIi8jCWMgIzRDNENCQyIsCiIoIwljICNERUM5Q0EiLAoiXyMJYyAjREFCMkIyIiwKIjojCWMgIzY5NTFBNiIsCiI8IwljICM2OTRFQTYiLAoiWyMJYyAjNjU0Q0E1IiwKIn0jCWMgI0I1ODdBOSIsCiJ8IwljICNFNEFDQUQiLAoiMSMJYyAjRTVBREFDIiwKIjIjCWMgI0VBQUJBQiIsCiIzIwljICNFQ0FCQUMiLAoiNCMJYyAjRUZBREFDIiwKIjUjCWMgI0Y1QjBCMSIsCiI2IwljICNGOEIyQjIiLAoiNyMJYyAjRkJCNEI0IiwKIjgjCWMgI0ZGQzFDMSIsCiI5IwljICNGRkM0QzMiLAoiMCMJYyAjRkZDNUM1IiwKImEjCWMgI0ZEQzZDNiIsCiJiIwljICNFQkM4QzkiLAoiYyMJYyAjNEU0OUFDIiwKImQjCWMgIzVGNUVBOSIsCiJlIwljICNBQ0FEQUQiLAoiZiMJYyAjQUJBREFDIiwKImcjCWMgI0NDQ0RDQyIsCiJoIwljICNGQkZCRkIiLAoiaSMJYyAjOTM5M0Q3IiwKImojCWMgI0U5RTlGNiIsCiJrIwljICNGOEY2RjYiLAoibCMJYyAjREVDRUQwIiwKIm0jCWMgI0QxQjNCNSIsCiJuIwljICNDN0FGQUYiLAoibyMJYyAjNTk1MEE1IiwKInAjCWMgIzlBNzVBOCIsCiJxIwljICMxOTEzQTIiLAoiciMJYyAjRENBNkFCIiwKInMjCWMgI0U0QUNBQiIsCiJ0IwljICNFMkFEQUMiLAoidSMJYyAjREVBQ0FDIiwKInYjCWMgI0Q3QUNBRCIsCiJ3IwljICNENUFEQUUiLAoieCMJYyAjRDlBREFEIiwKInkjCWMgI0UyQURBRSIsCiJ6IwljICNFNkFEQUQiLAoiQSMJYyAjNkQ0RUE3IiwKIkIjCWMgI0YxQUVBRSIsCiJDIwljICNGNEFGQUYiLAoiRCMJYyAjRjlCMkIzIiwKIkUjCWMgI0ZDQjVCNSIsCiJGIwljICNGRkJGQkYiLAoiRyMJYyAjRkZDMkMyIiwKIkgjCWMgI0ZGQzVDNiIsCiJJIwljICNGRkM5QzkiLAoiSiMJYyAjRkVDQ0NCIiwKIksjCWMgI0ZEQ0VDRSIsCiJMIwljICNGM0QxRDMiLAoiTSMJYyAjNTM0REIwIiwKIk4jCWMgIzIxMjFBNSIsCiJPIwljICMzRDNEQTYiLAoiUCMJYyAjM0MzQ0E1IiwKIlEjCWMgIzQyNDJCMCIsCiJSIwljICMyODI4QUYiLAoiUyMJYyAjREJEQkYyIiwKIlQjCWMgI0VDRTFFMyIsCiJVIwljICNDRkJCQkUiLAoiViMJYyAjQkRCMUIzIiwKIlcjCWMgI0I5QjNCNCIsCiJYIwljICM1MzUxQTYiLAoiWSMJYyAjREFBNEFCIiwKIlojCWMgI0UyQUJBRCIsCiJgIwljICNEREFFQUMiLAoiICQJYyAjRDZCMkFEIiwKIi4kCWMgI0NBQjBBQyIsCiIrJAljICNDNEIxQUMiLAoiQCQJYyAjQkZCMUFDIiwKIiMkCWMgI0JFQjBBRCIsCiIkJAljICNCQkFDQUMiLAoiJSQJYyAjQzBBQ0FDIiwKIiYkCWMgI0NCQUNBRCIsCiIqJAljICNEOUFGQUYiLAoiPSQJYyAjRTVBRUFEIiwKIi0kCWMgIzZDNEZBNiIsCiI7JAljICNGMkFFQUUiLAoiPiQJYyAjRjRCMEIwIiwKIiwkCWMgI0ZBQjNCNCIsCiInJAljICNGRkI5QkEiLAoiKSQJYyAjRkZCREJEIiwKIiEkCWMgI0ZGQzZDNiIsCiJ+JAljICNGRkM5Q0EiLAoieyQJYyAjRkVDRENFIiwKIl0kCWMgI0ZFRDFEMSIsCiJeJAljICNGRUQ0RDQiLAoiLyQJYyAjRjZEN0Q4IiwKIigkCWMgIzU2NTFCMyIsCiJfJAljICNGMUVERUQiLAoiOiQJYyAjRDdDQ0NCIiwKIjwkCWMgI0JDQjJCMSIsCiJbJAljICNCMkI1QjMiLAoifSQJYyAjQjNCN0I3IiwKInwkCWMgIzUxNTFBOCIsCiIxJAljICM2QTRFQTYiLAoiMiQJYyAjRTJBQ0FGIiwKIjMkCWMgI0Q2QURBRSIsCiI0JAljICNDOUIyQUYiLAoiNSQJYyAjQkVCMkFEIiwKIjYkCWMgI0I5QjZCMCIsCiI3JAljICNCMUIyQUQiLAoiOCQJYyAjQURBRkFEIiwKIjkkCWMgI0IwQjJBRiIsCiIwJAljICNCMEIwQjAiLAoiYSQJYyAjQjNCMUIyIiwKImIkCWMgI0I3QjBCMSIsCiJjJAljICNEMEFGQUQiLAoiZCQJYyAjRTJBRUFEIiwKImUkCWMgIzZGNTFBNiIsCiJmJAljICM2RDRFQTYiLAoiZyQJYyAjRjJBRkFFIiwKImgkCWMgI0Y3QjJCMiIsCiJpJAljICNGRUI3QjgiLAoiaiQJYyAjRkZCQUJCIiwKImskCWMgI0ZGQzNDMyIsCiJsJAljICNGRkM4QzgiLAoibSQJYyAjRkZDQ0NEIiwKIm4kCWMgI0ZGRDJEMyIsCiJvJAljICNGRkQ3RDciLAoicCQJYyAjRkVEQURCIiwKInEkCWMgI0Y5REVERiIsCiJyJAljICM1OTU1QjciLAoicyQJYyAjMjIyMUE3IiwKInQkCWMgIzNEM0RBQiIsCiJ1JAljICMzQTNBQTgiLAoidiQJYyAjMzczN0E1IiwKInckCWMgIzM2MzZBNCIsCiJ4JAljICMyMzIzQTYiLAoieSQJYyAjREVEMkQyIiwKInokCWMgI0MyQjhCNSIsCiJBJAljICNCOUI4QjEiLAoiQiQJYyAjQjlCOUIyIiwKIkMkCWMgI0I3QjhCNCIsCiJEJAljICM1MTUxQTciLAoiRSQJYyAjRTRBREFGIiwKIkYkCWMgI0Q2QURBRiIsCiJHJAljICNDNUIwQUYiLAoiSCQJYyAjQjhCNUIyIiwKIkkkCWMgI0IyQjJCMSIsCiJKJAljICNCMkIzQjIiLAoiSyQJYyAjQjNCNEIzIiwKIkwkCWMgI0I0QjRCNCIsCiJNJAljICNCNUI1QjUiLAoiTiQJYyAjQjlCOUI5IiwKIk8kCWMgI0JBQjlCQSIsCiJQJAljICNCQ0JCQkQiLAoiUSQJYyAjQUVBQ0FDIiwKIlIkCWMgI0QxQUVBRSIsCiJTJAljICM2RDUxQTYiLAoiVCQJYyAjNkU0RUE2IiwKIlUkCWMgI0YxQURBRCIsCiJWJAljICNGQkI1QjUiLAoiVyQJYyAjRkVCOEI4IiwKIlgkCWMgI0ZGQkJCQyIsCiJZJAljICNGRkMwQzAiLAoiWiQJYyAjRkZDQUNBIiwKImAkCWMgI0ZGQ0VDRiIsCiIgJQljICNGRkQ1RDUiLAoiLiUJYyAjRkVEQURBIiwKIislCWMgI0ZFREZERiIsCiJAJQljICNGQkU0RTQiLAoiIyUJYyAjNUM1OEJBIiwKIiQlCWMgIzcyNzJCRCIsCiIlJQljICNDQ0NBQ0MiLAoiJiUJYyAjQzJDMEMwIiwKIiolCWMgI0I2QjVCNiIsCiI9JQljICNBRUFFQUUiLAoiLSUJYyAjNzM3M0E5IiwKIjslCWMgI0U5RTRFNCIsCiI+JQljICNDQ0MwQkUiLAoiLCUJYyAjQkNCNUFEIiwKIiclCWMgI0MwQjlBRiIsCiIpJQljICNDNEI3QjEiLAoiISUJYyAjQkNCNkFGIiwKIn4lCWMgIzUyNTBBNSIsCiJ7JQljICNEOEFFQUYiLAoiXSUJYyAjQzJCNUIxIiwKIl4lCWMgI0I0QjBBRSIsCiIvJQljICNBRkFGQUYiLAoiKCUJYyAjQjFCMkI0IiwKIl8lCWMgI0IzQjNCNSIsCiI6JQljICNCMkIyQjQiLAoiPCUJYyAjQjJCMkIyIiwKIlslCWMgI0FGQUVBRSIsCiJ9JQljICNBQ0FCQUIiLAoifCUJYyAjQUNBQ0FCIiwKIjElCWMgI0FFQUJBQiIsCiIyJQljICNCQkFCQUIiLAoiMyUJYyAjNjg1MkE5IiwKIjQlCWMgI0YyQUZBRiIsCiI1JQljICNGRkMwQzEiLAoiNiUJYyAjRkZDQkNDIiwKIjclCWMgI0ZGRDFEMiIsCiI4JQljICNGRkQ4RDgiLAoiOSUJYyAjRkZERERFIiwKIjAlCWMgI0ZGRTNFNCIsCiJhJQljICNGREU4RTgiLAoiYiUJYyAjNUY1QkJEIiwKImMlCWMgIzc3NzdDMiIsCiJkJQljICNENUQ1RDYiLAoiZSUJYyAjQ0JDQUNBIiwKImYlCWMgI0JEQkRCRCIsCiJnJQljICM4Nzg3QUEiLAoiaCUJYyAjRkVGRUZGIiwKImklCWMgI0Y2RjNGNCIsCiJqJQljICNEOUQyRDIiLAoiayUJYyAjQkJCOEI2IiwKImwlCWMgI0JFQkNCMSIsCiJtJQljICNDNUMwQjMiLAoibiUJYyAjQzJCQUI1IiwKIm8lCWMgIzU0NTBBNSIsCiJwJQljICNERkFEQUYiLAoicSUJYyAjQjdCMUFEIiwKInIlCWMgI0IzQjNCMiIsCiJzJQljICNBQ0FCQUMiLAoidCUJYyAjQUJBQ0FDIiwKInUlCWMgI0FCQUJBQiIsCiJ2JQljICNCMUIxQjAiLAoidyUJYyAjQURBQ0FCIiwKInglCWMgI0IzQUNBQiIsCiJ5JQljICM2MDUxQTciLAoieiUJYyAjNkQ0RkE2IiwKIkElCWMgI0Y2QjJCMiIsCiJCJQljICNGQUI1QjUiLAoiQyUJYyAjRkZDQ0NDIiwKIkQlCWMgI0ZGRDJEMiIsCiJFJQljICNGRkRFREYiLAoiRiUJYyAjRkZFNUU2IiwKIkclCWMgI0ZFRTlFQSIsCiJIJQljICM2MDVEQkYiLAoiSSUJYyAjN0I3QkM3IiwKIkolCWMgI0REREVERiIsCiJLJQljICNENEQ0RDMiLAoiTCUJYyAjQzRDNEM0IiwKIk0lCWMgI0FDQUNBRiIsCiJOJQljICM1MzUzQTYiLAoiTyUJYyAjNzk3OUJDIiwKIlAlCWMgI0U3RTNFMiIsCiJRJQljICNDOUMxQzAiLAoiUiUJYyAjQjdCOUIyIiwKIlMlCWMgI0M4Q0FCNSIsCiJUJQljICNEOUQ3QkYiLAoiVSUJYyAjQkZDMUI3IiwKIlYlCWMgI0IwQUZBRSIsCiJXJQljICM1ODUwQTUiLAoiWCUJYyAjRDhCMEIxIiwKIlklCWMgI0JDQUVBRSIsCiJaJQljICNCQkI3QjUiLAoiYCUJYyAjQjZCNkIzIiwKIiAmCWMgI0I3QjdCNCIsCiIuJgljICNCMkIwQjAiLAoiKyYJYyAjQUVCMEFGIiwKIkAmCWMgI0IwQjJCMSIsCiIjJgljICNBRUFFQUQiLAoiJCYJYyAjQjdCNkFGIiwKIiUmCWMgIzVCNTFBNiIsCiImJgljICNGMUFGQUYiLAoiKiYJYyAjRjNCMEIwIiwKIj0mCWMgI0ZEQjhCOCIsCiItJgljICNGRkQ5RDgiLAoiOyYJYyAjRkZERkRGIiwKIj4mCWMgI0ZGRTZFNyIsCiIsJgljICNGRUVDRUMiLAoiJyYJYyAjNjI1RUMwIiwKIikmCWMgIzdFN0ZDQSIsCiIhJgljICNFNEU2RTYiLAoifiYJYyAjREJEQ0RDIiwKInsmCWMgI0NFQ0VDRSIsCiJdJgljICNDMUMxQzEiLAoiXiYJYyAjQURBREFEIiwKIi8mCWMgI0JCQkJCQiIsCiIoJgljICNGMUYxRjEiLAoiXyYJYyAjRTBEQUQ5IiwKIjomCWMgI0MyQjlCNiIsCiI8JgljICNDMkMxQjIiLAoiWyYJYyAjRTJERUMwIiwKIn0mCWMgI0UzREJCQyIsCiJ8JgljICNDOUM3QjkiLAoiMSYJYyAjQjFBRUFDIiwKIjImCWMgIzVENTFBNiIsCiIzJgljICNEMUIwQjEiLAoiNCYJYyAjQjdCMEIwIiwKIjUmCWMgI0JGQkRCQyIsCiI2JgljICNDMEMwQkIiLAoiNyYJYyAjQjVCNkIyIiwKIjgmCWMgI0IyQjJCMyIsCiI5JgljICNCNEIyQjMiLAoiMCYJYyAjQUNBQ0FDIiwKImEmCWMgI0I1QjZCNiIsCiJiJgljICNCNEI2QjUiLAoiYyYJYyAjQjFCMkIxIiwKImQmCWMgI0FFQUVBQyIsCiJlJgljICM1QTUxQTYiLAoiZiYJYyAjRjlCNEI0IiwKImcmCWMgI0ZEQjdCOCIsCiJoJgljICNGRkNCQ0IiLAoiaSYJYyAjRkZEMUQxIiwKImomCWMgIzYyNUZDMSIsCiJrJgljICM4MTgxQ0MiLAoibCYJYyAjRUFFQkVBIiwKIm0mCWMgI0UwRTJFMiIsCiJuJgljICNEM0Q0RDQiLAoibyYJYyAjQzZDNkM2IiwKInAmCWMgI0I4QjhCOCIsCiJxJgljICNEQkRCREIiLAoiciYJYyAjRURFN0U2IiwKInMmCWMgI0QzQzhDOCIsCiJ0JgljICNCRUI2QjUiLAoidSYJYyAjRERENUMwIiwKInYmCWMgI0VEREFCRiIsCiJ3JgljICNFNUNBQjciLAoieCYJYyAjQ0NCOEIyIiwKInkmCWMgIzY1NTJBNyIsCiJ6JgljICNFN0FEQUIiLAoiQSYJYyAjRTFBRUFEIiwKIkImCWMgI0NBQjBCMSIsCiJDJgljICNCOUI0QjQiLAoiRCYJYyAjQjRCM0FGIiwKIkUmCWMgI0I1QjVCMiIsCiJGJgljICNCMEIxQjAiLAoiRyYJYyAjQkRCREJBIiwKIkgmCWMgI0IxQjFBRSIsCiJJJgljICNCMEFGQUQiLAoiSiYJYyAjQjFBRkFGIiwKIksmCWMgI0JCQjlCQiIsCiJMJgljICNCOUI2QjciLAoiTSYJYyAjQjlCN0I2IiwKIk4mCWMgI0FGQUVBRCIsCiJPJgljICNBRUFGQUQiLAoiUCYJYyAjQjhCOUIzIiwKIlEmCWMgIzU5NTFBNiIsCiJSJgljICNGMEFDQUQiLAoiUyYJYyAjRjJBRkIwIiwKIlQmCWMgI0Y1QjFCMSIsCiJVJgljICNGOUIzQjQiLAoiViYJYyAjRkRCNkI3IiwKIlcmCWMgI0ZGQzNDNCIsCiJYJgljICNGRkQwQ0YiLAoiWSYJYyAjRkZEN0Q2IiwKIlomCWMgI0ZFRUJFQiIsCiJgJgljICM4MzgzQ0QiLAoiICoJYyAjRUZFRkVGIiwKIi4qCWMgI0U2RTdFNyIsCiIrKgljICNEOURBREEiLAoiQCoJYyAjQ0RDRENEIiwKIiMqCWMgI0JFQkVCRSIsCiIkKgljICNCM0IzQjMiLAoiJSoJYyAjRjlGOUY5IiwKIiYqCWMgI0VERTFFMSIsCiIqKgljICNDQ0JFQkYiLAoiPSoJYyAjQjVCQUI5IiwKIi0qCWMgI0M5RDBDNCIsCiI7KgljICNFMEQ3QzciLAoiPioJYyAjREJDNUI5IiwKIiwqCWMgI0NBQjRCMCIsCiInKgljICNDQkFDQUIiLAoiKSoJYyAjNkI1MkE3IiwKIiEqCWMgI0UyQUVBRSIsCiJ+KgljICNCNkIzQjIiLAoieyoJYyAjQjNCM0IxIiwKIl0qCWMgI0JEQkRCNyIsCiJeKgljICNCRUJEQjYiLAoiLyoJYyAjQjhCN0IzIiwKIigqCWMgI0IyQjFCMSIsCiJfKgljICNCOEI3QjciLAoiOioJYyAjQkRCQUJBIiwKIjwqCWMgI0IwQUVBRCIsCiJbKgljICNCNUI3QjEiLAoifSoJYyAjRjhCMkIzIiwKInwqCWMgI0ZDQjVCNiIsCiIxKgljICNGRUI5QkEiLAoiMioJYyAjRkZCREJFIiwKIjMqCWMgI0ZGQzJDMyIsCiI0KgljICNGRkM3QzgiLAoiNSoJYyAjRkZDRUNEIiwKIjYqCWMgI0ZGRDVENCIsCiI3KgljICNGRURCREIiLAoiOCoJYyAjRkVFM0UzIiwKIjkqCWMgI0ZFRTlFOSIsCiIwKgljICM4MzgzQ0UiLAoiYSoJYyAjRjFGMEYwIiwKImIqCWMgI0U5RUFFQSIsCiJjKgljICNEREREREQiLAoiZCoJYyAjRDFEMUQxIiwKImUqCWMgI0I2QjZCNiIsCiJmKgljICNFOEU4RTgiLAoiZyoJYyAjQzhDOEM4IiwKImgqCWMgI0M3QzdDNyIsCiJpKgljICNGNEY0RjQiLAoiaioJYyAjRkFGOEY4IiwKImsqCWMgI0U3RDNENCIsCiJsKgljICNDQ0I3QjgiLAoibSoJYyAjQjhDNUMzIiwKIm4qCWMgI0M1REFDRiIsCiJvKgljICNENERCQ0YiLAoicCoJYyAjQkVCMkIxIiwKInEqCWMgI0M0QUJBQyIsCiJyKgljICM3MDUxQTYiLAoicyoJYyAjRTVBREFEIiwKInQqCWMgI0M5QUZBRSIsCiJ1KgljICNBREFEQUMiLAoidioJYyAjQjJCMUFGIiwKIncqCWMgI0JDQkJCNiIsCiJ4KgljICNCN0I3QjMiLAoieSoJYyAjQkFCQUI4IiwKInoqCWMgI0I5QkFCOCIsCiJBKgljICNCOUI5QjgiLAoiQioJYyAjQkNCN0IxIiwKIkMqCWMgIzVGNTJBNiIsCiJEKgljICNGQUI0QjUiLAoiRSoJYyAjRkRCOEI5IiwKIkYqCWMgI0ZFQkNCQyIsCiJHKgljICNGRkQyRDEiLAoiSCoJYyAjRkVEOEQ3IiwKIkkqCWMgI0ZGRTVFNSIsCiJKKgljICM2MTVEQkYiLAoiSyoJYyAjODI4MUNDIiwKIkwqCWMgI0YwRUZGMCIsCiJNKgljICNFQUVBRUEiLAoiTioJYyAjREZERkRGIiwKIk8qCWMgI0Q0RDRENCIsCiJQKgljICNDNUM1QzUiLAoiUSoJYyAjREVERURFIiwKIlIqCWMgI0Q2RDZENiIsCiJTKgljICNEOEQ4RDgiLAoiVCoJYyAjQ0FDQUNBIiwKIlUqCWMgI0UyQzVDNiIsCiJWKgljICNEMEIwQjAiLAoiVyoJYyAjQzRDQ0M2IiwKIlgqCWMgIzlCQTdDOCIsCiJZKgljICM0NDQ2QUMiLAoiWioJYyAjMkUyQkE0IiwKImAqCWMgIzM2MkJBNSIsCiIgPQljICMzQjJCQTUiLAoiLj0JYyAjMUMxNEEyIiwKIis9CWMgIzFCMTNBMiIsCiJAPQljICMzQjJCQTQiLAoiIz0JYyAjNDgzNkE0IiwKIiQ9CWMgIzk2ODBBQiIsCiIlPQljICNCN0I0QjEiLAoiJj0JYyAjQUJBQkFDIiwKIio9CWMgI0FEQURBRiIsCiI9PQljICNBRUFFQjAiLAoiLT0JYyAjQUZCMUIyIiwKIjs9CWMgIzVBNUFBQyIsCiI+PQljICMzRTNFQTkiLAoiLD0JYyAjMkUyRUE3IiwKIic9CWMgIzJCMkJBNCIsCiIpPQljICMyQzJCQTQiLAoiIT0JYyAjMzAyQ0E0IiwKIn49CWMgIzFBMTVBMiIsCiJ7PQljICMxQjE0QTMiLAoiXT0JYyAjM0MyQkE0IiwKIl49CWMgIzNDMkNBNSIsCiIvPQljICMzRDJDQTUiLAoiKD0JYyAjNEUzOEE2IiwKIl89CWMgIzczNTNBOSIsCiI6PQljICNGM0IxQjciLAoiPD0JYyAjRkRCQkJCIiwKIls9CWMgI0ZFQkZCRiIsCiJ9PQljICNGRkM4QzkiLAoifD0JYyAjRkRDRENFIiwKIjE9CWMgIzgxNkNCQyIsCiIyPQljICM0NzNEQjEiLAoiMz0JYyAjNDAzOUIxIiwKIjQ9CWMgIzE4MTdBOCIsCiI1PQljICMzQzNDQjUiLAoiNj0JYyAjM0EzQUIzIiwKIjc9CWMgIzM4MzhCMSIsCiI4PQljICMzOTM5QUYiLAoiOT0JYyAjNjk2OUI1IiwKIjA9CWMgI0MwQzBDMCIsCiJhPQljICNEQURBREEiLAoiYj0JYyAjRUZFQUVBIiwKImM9CWMgI0U0QkZCRiIsCiJkPQljICNEQkFGQUQiLAoiZT0JYyAjQkVCN0IzIiwKImY9CWMgIzMzMzJBQSIsCiJnPQljICMzMTI3QTQiLAoiaD0JYyAjQzJBRkFFIiwKImk9CWMgI0FEQUJBQyIsCiJqPQljICNBQkFDQUQiLAoiaz0JYyAjQUVBREFFIiwKImw9CWMgIzkyOTNBRCIsCiJtPQljICNCOTg2QjAiLAoibj0JYyAjRkNCOUI5IiwKIm89CWMgI0ZFQkRCRCIsCiJwPQljICNFMEIyQzciLAoicT0JYyAjQUFBQUI5IiwKInI9CWMgI0IxQjFCMSIsCiJzPQljICNGM0YzRjMiLAoidD0JYyAjRDNEM0QzIiwKInU9CWMgI0U0REFEQiIsCiJ2PQljICNFN0JCQkMiLAoidz0JYyAjRUJBRkFFIiwKIng9CWMgI0Q0QUNBQyIsCiJ5PQljICM3QzY1QTciLAoiej0JYyAjMEIwOUEyIiwKIkE9CWMgIzA5MDdBMiIsCiJCPQljICM3QjVFQTgiLAoiQz0JYyAjRDBBQ0FEIiwKIkQ9CWMgI0IxQUJBQiIsCiJFPQljICNBRkFGQUUiLAoiRj0JYyAjQjNCMkIwIiwKIkc9CWMgI0IxQjBCMiIsCiJIPQljICMyODI4QTMiLAoiST0JYyAjMEUwQUEyIiwKIko9CWMgIzMyMjRBNCIsCiJLPQljICNFMkE0QjIiLAoiTD0JYyAjRkFCN0I3IiwKIk09CWMgI0ZDQkFCQSIsCiJOPQljICNGRUJFQkUiLAoiTz0JYyAjRkZDN0M5IiwKIlA9CWMgIzQ3MzlBRCIsCiJRPQljICMzNTM1QUIiLAoiUj0JYyAjQkJCQkJDIiwKIlM9CWMgI0JBQkFCQSIsCiJUPQljICNGOEY4RjgiLAoiVT0JYyAjRTREM0QzIiwKIlY9CWMgI0VBQjhCOCIsCiJXPQljICNGNkFDQUMiLAoiWD0JYyAjRjVBREFFIiwKIlk9CWMgI0Y0QUNBRCIsCiJaPQljICNGNUFCQUQiLAoiYD0JYyAjRjRBQkFDIiwKIiAtCWMgI0YyQUJBQiIsCiIuLQljICNGMUFCQUQiLAoiKy0JYyAjRjBBQkFDIiwKIkAtCWMgI0VBQUNBQyIsCiIjLQljICNDN0FDQUMiLAoiJC0JYyAjQjVCMkIxIiwKIiUtCWMgI0IyQjNCMSIsCiImLQljICNBRkFEQUUiLAoiKi0JYyAjQjBBQ0FEIiwKIj0tCWMgI0JEQjFCMiIsCiItLQljICNDM0FDQUMiLAoiOy0JYyAjRENBRUFFIiwKIj4tCWMgI0U4QUNBQyIsCiIsLQljICNFQkFDQUQiLAoiJy0JYyAjRUNBQ0FFIiwKIiktCWMgI0VEQUVBRiIsCiIhLQljICNFRkFGQUYiLAoifi0JYyAjRjFCMEIxIiwKInstCWMgI0YzQjNCMiIsCiJdLQljICNGNkI1QjUiLAoiXi0JYyAjRjlCOEI4IiwKIi8tCWMgI0ZCQkJCQyIsCiIoLQljICNGQkJGQzAiLAoiXy0JYyAjRkJDM0M0IiwKIjotCWMgI0ZCQzhDOCIsCiI8LQljICNGQkNEQ0QiLAoiWy0JYyAjRkJEMkQzIiwKIn0tCWMgI0VERDZENiIsCiJ8LQljICNEQ0Q5RDgiLAoiMS0JYyAjRENEQ0RDIiwKIjItCWMgI0Q5REFEOSIsCiIzLQljICNENUQ1RDUiLAoiNC0JYyAjQ0ZDRkNGIiwKIjUtCWMgI0JDQkNCQyIsCiI2LQljICNFNEU0RTQiLAoiNy0JYyAjRTlEMEQxIiwKIjgtCWMgI0VBQjNCNCIsCiI5LQljICNGN0FCQUMiLAoiMC0JYyAjRkFBQkFCIiwKImEtCWMgI0Y5QUJBQyIsCiJiLQljICNGOEFCQUQiLAoiYy0JYyAjRjZBQkFDIiwKImQtCWMgI0Y1QUJBQiIsCiJlLQljICNGNEFCQUIiLAoiZi0JYyAjRjBBQkFCIiwKImctCWMgI0VGQUJBQiIsCiJoLQljICNFRUFCQUIiLAoiaS0JYyAjRURBQkFCIiwKImotCWMgI0UxQURCMCIsCiJrLQljICNDRkFFQUYiLAoibC0JYyAjQjlBQkFCIiwKIm0tCWMgI0IxQUNBQiIsCiJuLQljICNCMUFDQUQiLAoiby0JYyAjQjJBQ0FEIiwKInAtCWMgI0IxQURBRCIsCiJxLQljICNCNEFEQUQiLAoici0JYyAjQkJBREFEIiwKInMtCWMgI0NGQjBBRiIsCiJ0LQljICNEQkFEQUMiLAoidS0JYyAjRTZBQkFEIiwKInYtCWMgI0U3QUNBRCIsCiJ3LQljICNFOUFEQUUiLAoieC0JYyAjRUFBRUFGIiwKInktCWMgI0VDQjBCMCIsCiJ6LQljICNFRUIyQjEiLAoiQS0JYyAjRjFCNEIzIiwKIkItCWMgI0Y0QjZCNiIsCiJDLQljICNGNkI5QkEiLAoiRC0JYyAjRjZCQ0JEIiwKIkUtCWMgI0Y2QzBDMCIsCiJGLQljICNGN0M0QzQiLAoiRy0JYyAjRjdDOEM4IiwKIkgtCWMgI0Y3Q0NDRCIsCiJJLQljICNFN0QwRDAiLAoiSi0JYyAjRDREMUQwIiwKIkstCWMgI0Q0RDNENCIsCiJMLQljICNEMkQyRDIiLAoiTS0JYyAjQzJDMkMyIiwKIk4tCWMgI0VEQ0VDRSIsCiJPLQljICNFREIxQjMiLAoiUC0JYyAjRjhBQ0FFIiwKIlEtCWMgI0Y5QUJBQiIsCiJSLQljICNGOEFCQUMiLAoiUy0JYyAjRjdBQ0FCIiwKIlQtCWMgI0Y2QUNBQiIsCiJVLQljICNGM0FCQUMiLAoiVi0JYyAjRjBBQkFEIiwKIlctCWMgI0VEQUNBQiIsCiJYLQljICNFN0FDQUMiLAoiWS0JYyAjRTRBREFEIiwKIlotCWMgI0REQUZBRSIsCiJgLQljICNEM0FDQUMiLAoiIDsJYyAjQzlBQ0FEIiwKIi47CWMgI0M3QURBQyIsCiIrOwljICNDQ0FDQUMiLAoiQDsJYyAjREFBRkFFIiwKIiM7CWMgI0REQURBQyIsCiIkOwljICNEREFDQUMiLAoiJTsJYyAjRENBQkFDIiwKIiY7CWMgI0REQUJBQiIsCiIqOwljICNERkFCQUIiLAoiPTsJYyAjRTBBQ0FDIiwKIi07CWMgI0UxQUNBQyIsCiI7OwljICNFMkFEQUQiLAoiPjsJYyAjRTNBRUFFIiwKIiw7CWMgI0U1QUZBRiIsCiInOwljICNFN0IwQjAiLAoiKTsJYyAjRTlCMkIxIiwKIiE7CWMgI0VCQjNCMyIsCiJ+OwljICNFRUI2QjYiLAoiezsJYyAjRUZCOUI5IiwKIl07CWMgI0YwQkNCQyIsCiJeOwljICNGMEJGQkYiLAoiLzsJYyAjRjBDMkMyIiwKIig7CWMgI0YwQzVDNiIsCiJfOwljICNERkM4QzgiLAoiOjsJYyAjQ0FDN0M3IiwKIjw7CWMgI0M5QzhDOSIsCiJbOwljICNCN0I3QjciLAoifTsJYyAjRDlEOUQ5IiwKInw7CWMgI0VEQ0NDRCIsCiIxOwljICNGOEFDQUYiLAoiMjsJYyAjRjhBQ0FEIiwKIjM7CWMgI0Y3QUJBQiIsCiI0OwljICNGM0FDQUIiLAoiNTsJYyAjRUJBQ0FDIiwKIjY7CWMgI0RGQUVCMCIsCiI3OwljICNEREFGQUYiLAoiODsJYyAjREVBRkFFIiwKIjk7CWMgI0UwQUVBRCIsCiIwOwljICNFMEFEQUQiLAoiYTsJYyAjREZBREFEIiwKImI7CWMgI0REQUNBRCIsCiJjOwljICNEQUFDQUMiLAoiZDsJYyAjRDhBQkFDIiwKImU7CWMgI0Q2QUJBQyIsCiJmOwljICNEN0FDQUIiLAoiZzsJYyAjRDhBQ0FCIiwKImg7CWMgI0Q5QUNBQyIsCiJpOwljICNEOUFDQUQiLAoiajsJYyAjREJBREFFIiwKIms7CWMgI0RGQUZCMCIsCiJsOwljICNFMUIxQjEiLAoibTsJYyAjRTJCM0IyIiwKIm47CWMgI0U1QjVCNSIsCiJvOwljICNFNkI3QjciLAoicDsJYyAjRTdCOUJBIiwKInE7CWMgI0U3QkNCQyIsCiJyOwljICNFN0JGQkYiLAoiczsJYyAjRTdDMEMwIiwKInQ7CWMgI0Q4QzJDMiIsCiJ1OwljICNDM0JGQzAiLAoidjsJYyAjQzFDMEMxIiwKInc7CWMgI0MxQzBDMCIsCiJ4OwljICNCRkJGQkYiLAoieTsJYyAjRUJDQ0NDIiwKIno7CWMgI0U4QUZCMCIsCiJBOwljICNEQkFCQUIiLAoiQjsJYyAjRDlBQkFCIiwKIkM7CWMgI0Q1QUJBQyIsCiJEOwljICNEMkFCQUMiLAoiRTsJYyAjQ0ZBQkFCIiwKIkY7CWMgI0NEQUJBQiIsCiJHOwljICNDQ0FCQUIiLAoiSDsJYyAjQ0VBQkFCIiwKIkk7CWMgI0QwQUJBQiIsCiJKOwljICNEMkFCQUIiLAoiSzsJYyAjRDNBQkFCIiwKIkw7CWMgI0QyQUNBQiIsCiJNOwljICNENUFCQUQiLAoiTjsJYyAjRDVBQ0FEIiwKIk87CWMgI0Q2QUVBRCIsCiJQOwljICNEOEFGQjAiLAoiUTsJYyAjRDlCMEIxIiwKIlI7CWMgI0RBQjFCMiIsCiJTOwljICNEQUIzQjQiLAoiVDsJYyAjREFCNUI0IiwKIlU7CWMgI0RBQjZCNSIsCiJWOwljICNDRUI5QjkiLAoiVzsJYyAjQkVCOUJBIiwKIlg7CWMgI0JCQjlCQSIsCiJZOwljICNCQkI5QjkiLAoiWjsJYyAjQkFCQkJCIiwKImA7CWMgI0VBQ0RDQyIsCiIgPgljICNFNkIyQjEiLAoiLj4JYyAjRURBRUFEIiwKIis+CWMgI0VCQUVBRSIsCiJAPgljICNFOUFFQUUiLAoiIz4JYyAjRUFBRUFFIiwKIiQ+CWMgI0VBQURBRCIsCiIlPgljICNFOEFFQUUiLAoiJj4JYyAjRTdBRUFEIiwKIio+CWMgI0U2QUVBRCIsCiI9PgljICNFNUFEQUUiLAoiLT4JYyAjRTZBREFGIiwKIjs+CWMgI0U1QURBRiIsCiI+PgljICNFM0FEQUMiLAoiLD4JYyAjRTFBREFDIiwKIic+CWMgI0RGQURBQyIsCiIpPgljICNERUFEQUMiLAoiIT4JYyAjRENBREFDIiwKIn4+CWMgI0RCQURBRCIsCiJ7PgljICNEQkFDQUMiLAoiXT4JYyAjRDVBQ0FDIiwKIl4+CWMgI0QxQUNBQyIsCiIvPgljICNDQ0FDQUIiLAoiKD4JYyAjQ0FBQ0FCIiwKIl8+CWMgI0NBQUNBQyIsCiI6PgljICNDREFDQUMiLAoiPD4JYyAjQ0VBQ0FDIiwKIls+CWMgI0NGQUNBQiIsCiJ9PgljICNDRkFDQUMiLAoifD4JYyAjRDFBQkFDIiwKIjE+CWMgI0QyQUNBQyIsCiIyPgljICNEM0FDQUQiLAoiMz4JYyAjRDRBREFCIiwKIjQ+CWMgI0Q1QUVBRiIsCiI1PgljICNEQUIzQjIiLAoiNj4JYyAjQ0RCNkI2IiwKIjc+CWMgI0JBQjZCNyIsCiI4PgljICNCOEI3QjYiLAoiOT4JYyAjQjdCN0I4IiwKIjA+CWMgI0VEQ0RDRCIsCiJhPgljICNFRUIyQjIiLAoiYj4JYyAjRkFBREFEIiwKImM+CWMgI0Y5QURBQyIsCiJkPgljICNGN0FDQUUiLAoiZT4JYyAjRjZBREFDIiwKImY+CWMgI0Y1QUNBQiIsCiJnPgljICNGNUFDQUMiLAoiaD4JYyAjRjFBQ0FEIiwKImk+CWMgI0YwQUJBRSIsCiJqPgljICNFREFDQUQiLAoiaz4JYyAjRUNBQ0FDIiwKImw+CWMgI0U2QUNBRCIsCiJtPgljICNFNUFDQUQiLAoibj4JYyAjRTNBQ0FDIiwKIm8+CWMgI0Q2QUNBQiIsCiJwPgljICNEMEFDQUMiLAoicT4JYyAjRDBBQkFDIiwKInI+CWMgI0Q0QUJBQiIsCiJzPgljICNENEFCQUMiLAoidD4JYyAjRDVBQkFCIiwKInU+CWMgI0Q2QUJBQiIsCiJ2PgljICNEN0FCQUQiLAoidz4JYyAjRDhBREFCIiwKIng+CWMgI0Q4QUVBRCIsCiJ5PgljICNEQ0IwQjAiLAoiej4JYyAjRERCMEIwIiwKIkE+CWMgI0RFQjFCMSIsCiJCPgljICNERUIyQjIiLAoiQz4JYyAjQ0ZCNUI1IiwKIkQ+CWMgI0I1QjRCNCIsCiJFPgljICNCNUI1QjQiLAoiRj4JYyAjRDdEN0Q3IiwKIkc+CWMgI0YwQjFCMSIsCiJIPgljICNGQ0FCQUIiLAoiST4JYyAjRkNBQkFDIiwKIko+CWMgI0ZCQUJBQyIsCiJLPgljICNGNUFCQUMiLAoiTD4JYyAjRjFBQkFCIiwKIk0+CWMgI0REQUNBQiIsCiJOPgljICNEN0FCQUIiLAoiTz4JYyAjRDhBQkFCIiwKIlA+CWMgI0RBQUJBQyIsCiJRPgljICNEOUFDQUIiLAoiUj4JYyAjREFBREFCIiwKIlM+CWMgI0RDQURBQiIsCiJUPgljICNEREFEQUQiLAoiVT4JYyAjREZBRUFGIiwKIlY+CWMgI0UwQUZBRiIsCiJXPgljICNFMkIwQjAiLAoiWD4JYyAjRTNCMUIxIiwKIlk+CWMgI0QxQjRCNCIsCiJaPgljICNCOEIyQjMiLAoiYD4JYyAjQjRCM0IzIiwKIiAsCWMgI0I0QjRCMyIsCiIuLAljICNCNEIzQjQiLAoiKywJYyAjRUFEMUQwIiwKIkAsCWMgI0VFQjVCMyIsCiIjLAljICNGQ0FDQUMiLAoiJCwJYyAjRkJBQkFCIiwKIiUsCWMgI0Y4QUJBQiIsCiImLAljICNGM0FCQUIiLAoiKiwJYyAjREJBQkFDIiwKIj0sCWMgI0REQUJBRCIsCiItLAljICNERUFCQUQiLAoiOywJYyAjREVBQkFDIiwKIj4sCWMgI0UwQUJBQyIsCiIsLAljICNERUFEQUIiLAoiJywJYyAjRTBBREFCIiwKIiksCWMgI0UyQUNBRCIsCiIhLAljICNFM0FDQUUiLAoifiwJYyAjRTRBRUFGIiwKInssCWMgI0U2QUVBRiIsCiJdLAljICNFOEIxQjEiLAoiXiwJYyAjRDRCNEI0IiwKIi8sCWMgI0I4QjFCMiIsCiIoLAljICNCM0IyQjMiLAoiXywJYyAjQjNCMkIyIiwKIjosCWMgI0U2RDREMiIsCiI8LAljICNFQ0I5QjciLAoiWywJYyAjRkFBQ0FDIiwKIn0sCWMgI0ZDQUJBRiIsCiJ8LAljICNGOEFEQjAiLAoiMSwJYyAjRjVBREFGIiwKIjIsCWMgI0Y0QURBRCIsCiIzLAljICNFMkFCQUUiLAoiNCwJYyAjRTFBQkFEIiwKIjUsCWMgI0RFQURBRCIsCiI2LAljICNERkFEQUIiLAoiNywJYyAjRTFBREFCIiwKIjgsCWMgI0U4QUNBRiIsCiI5LAljICNFN0FEQUYiLAoiMCwJYyAjRThBREFFIiwKImEsCWMgI0VDQjBCMSIsCiJiLAljICNENUIzQjMiLAoiYywJYyAjRjJGMkYyIiwKImQsCWMgI0UwRTBFMCIsCiJlLAljICNGNkY2RjYiLAoiZiwJYyAjRjVFREVCIiwKImcsCWMgI0VDQkRCQiIsCiJoLAljICNGQUFDQUYiLAoiaSwJYyAjRjRBRkI1IiwKImosCWMgI0Q5QUZCNCIsCiJrLAljICNENEI3QjkiLAoibCwJYyAjRTZCM0IyIiwKIm0sCWMgI0Y2QUJBQiIsCiJuLAljICNGM0FCQUQiLAoibywJYyAjRTNBQkFEIiwKInAsCWMgI0UzQUNBQiIsCiJxLAljICNFMUFEQUQiLAoiciwJYyAjREFBRUFFIiwKInMsCWMgI0Q0QUZBRiIsCiJ0LAljICNEMUFGQUUiLAoidSwJYyAjRDFBRkFEIiwKInYsCWMgI0QyQUZBRCIsCiJ3LAljICNEOUFFQjEiLAoieCwJYyAjRTJBQ0FFIiwKInksCWMgI0U5QUNBRCIsCiJ6LAljICNFOUFDQUUiLAoiQSwJYyAjRUFBREFFIiwKIkIsCWMgI0VDQURBRSIsCiJDLAljICNFRUFEQUUiLAoiRCwJYyAjRUVBRUFGIiwKIkUsCWMgI0Q1QjFCMSIsCiJGLAljICNCNUFGQUUiLAoiRywJYyAjQjBCMEFGIiwKIkgsCWMgI0Y4RjNGMyIsCiJJLAljICNFQUJGQkYiLAoiSiwJYyAjRjZBRUIyIiwKIkssCWMgI0U5QjJCOSIsCiJMLAljICNDQkIxQkIiLAoiTSwJYyAjQkRCMUI5IiwKIk4sCWMgI0M0QjNCNiIsCiJPLAljICNENEI1QjUiLAoiUCwJYyAjRERBRkIwIiwKIlEsCWMgI0VFQUZBRSIsCiJSLAljICNFM0FDQUQiLAoiUywJYyAjRDhCMkFFIiwKIlQsCWMgI0NCQjNCMyIsCiJVLAljICNCREFDQUUiLAoiViwJYyAjQjhBQkFCIiwKIlcsCWMgI0I2QUJBQyIsCiJYLAljICNCNkFDQUQiLAoiWSwJYyAjQzNCNkI5IiwKIlosCWMgI0Q4QkJCQSIsCiJgLAljICNERUIzQjAiLAoiICcJYyAjRThBREFEIiwKIi4nCWMgI0VBQUNBRCIsCiIrJwljICNFQ0FDQUQiLAoiQCcJYyAjRUVBREFEIiwKIiMnCWMgI0VEQUVBRSIsCiIkJwljICNENEIwQjEiLAoiJScJYyAjQjJBREFEIiwKIiYnCWMgI0FFQUVBRiIsCiIqJwljICNBRUFGQUYiLAoiPScJYyAjRjBGMEYwIiwKIi0nCWMgI0ZBRjRGNCIsCiI7JwljICNFOEM0QzQiLAoiPicJYyAjRUVCMkI1IiwKIiwnCWMgI0RFQjNCQiIsCiInJwljICNDQ0I2Q0EiLAoiKScJYyAjQ0RCQkNEIiwKIiEnCWMgI0NGQjdCQyIsCiJ+JwljICNENEI5QjUiLAoieycJYyAjQzhBRkFEIiwKIl0nCWMgI0RFQjJBRSIsCiJeJwljICNGMkFEQUIiLAoiLycJYyAjREVBREFGIiwKIignCWMgI0RDQjZCNyIsCiJfJwljICNERUM3QzAiLAoiOicJYyAjRDFDRkNDIiwKIjwnCWMgI0I5QkNCRCIsCiJbJwljICNBQ0FCQUUiLAoifScJYyAjQUNBQkFEIiwKInwnCWMgI0FGQjBCNSIsCiIxJwljICNDNkNFRDEiLAoiMicJYyAjQ0VDNUJFIiwKIjMnCWMgI0RCQzZDMSIsCiI0JwljICNENUI1QjciLAoiNScJYyAjRTNBREFEIiwKIjYnCWMgI0VCQURBRCIsCiI3JwljICNEMkIwQjAiLAoiOCcJYyAjQjBBQ0FDIiwKIjknCWMgI0FEQURBRSIsCiIwJwljICM4Nzg3QUIiLAoiYScJYyAjMEUwRUEyIiwKImInCWMgIzA1MDVBMSIsCiJjJwljICM4MDdGQTkiLAoiZCcJYyAjRjVGNUY1IiwKImUnCWMgI0Y4RjRGNSIsCiJmJwljICNFOENEQ0QiLAoiZycJYyAjRTZCOEI5IiwKImgnCWMgI0Q2QjJCQiIsCiJpJwljICNDM0IzQ0UiLAoiaicJYyAjQ0JCN0NGIiwKImsnCWMgI0RFQkFCRCIsCiJsJwljICNFQUMzQjYiLAoibScJYyAjRTFDMkI2IiwKIm4nCWMgI0YxQ0JCQyIsCiJvJwljICNGMUJBQUUiLAoicCcJYyAjRjJBQ0FCIiwKInEnCWMgI0RGQURBRSIsCiJyJwljICNDREIwQjQiLAoicycJYyAjRDdDOEM3IiwKInQnCWMgI0QwQkRCMyIsCiJ1JwljICNDRUNBQzQiLAoidicJYyAjQjhCQUJBIiwKIncnCWMgI0FCQUNBRSIsCiJ4JwljICNBQkFCQUQiLAoieScJYyAjQUNBRUIxIiwKInonCWMgI0JFQzVDNyIsCiJBJwljICNEM0M5QzAiLAoiQicJYyAjRDZDREM4IiwKIkMnCWMgI0JEQjRCOCIsCiJEJwljICNEOEFFQUUiLAoiRScJYyAjRDBBRkFGIiwKIkYnCWMgI0FGQUNBQiIsCiJHJwljICNBQ0FDQUQiLAoiSCcJYyAjNzk3OUE5IiwKIkknCWMgIzAzMDNBMSIsCiJKJwljICM2RjZFQTciLAoiSycJYyAjRjBERkRGIiwKIkwnCWMgI0UyQkVCRSIsCiJNJwljICNEOEIzQjgiLAoiTicJYyAjQzhCNkNFIiwKIk8nCWMgI0M5QjVDQiIsCiJQJwljICNEQUI1QkIiLAoiUScJYyAjRTdCQkI0IiwKIlInCWMgI0U2QzFCNSIsCiJTJwljICNGNUQ1QkUiLAoiVCcJYyAjRkFEMUI4IiwKIlUnCWMgI0YxQjFBQyIsCiJWJwljICNFMkFCQUMiLAoiVycJYyAjRDVBRUFFIiwKIlgnCWMgI0I4QUNCMCIsCiJZJwljICNDNUNGQ0MiLAoiWicJYyAjQ0NEOEM4IiwKImAnCWMgI0I5QzNDOCIsCiIgKQljICNCNUI5QzAiLAoiLikJYyAjQkRDMUMyIiwKIispCWMgI0IxQjdCRCIsCiJAKQljICNBREIxQjgiLAoiIykJYyAjQkZDMkMyIiwKIiQpCWMgI0M2QzlDNyIsCiIlKQljICNCNkJGQzUiLAoiJikJYyAjQzlEMEM4IiwKIiopCWMgI0NERDVEMCIsCiI9KQljICNCM0I1QjkiLAoiLSkJYyAjQzRBQ0FDIiwKIjspCWMgI0U3QUNBQiIsCiI+KQljICNDRUFFQUYiLAoiLCkJYyAjQUZBQkFCIiwKIicpCWMgI0E5QUFBQyIsCiIpKQljICM5QzlCQUEiLAoiISkJYyAjMTMxM0EyIiwKIn4pCWMgIzZFNkVBNyIsCiJ7KQljICNGNEVGRUYiLAoiXSkJYyAjRTRDOEM4IiwKIl4pCWMgI0REQjBCNSIsCiIvKQljICNDQ0I1Q0EiLAoiKCkJYyAjQ0NCOENDIiwKIl8pCWMgI0RBQjZCQyIsCiI6KQljICNFOEJBQjUiLAoiPCkJYyAjRTdCRkIxIiwKIlspCWMgI0YzRDNCNiIsCiJ9KQljICNGOUQ1QjIiLAoifCkJYyAjRjZDMEIwIiwKIjEpCWMgI0YyQUVBQiIsCiIyKQljICNDMkFDQUQiLAoiMykJYyAjQjJBRkIxIiwKIjQpCWMgI0M3Q0RDNyIsCiI1KQljICNDREQ1QzQiLAoiNikJYyAjQkNDQ0NGIiwKIjcpCWMgI0M4Q0NDRCIsCiI4KQljICNDOUM1QzEiLAoiOSkJYyAjQzJDQkNGIiwKIjApCWMgI0I0QkVDOCIsCiJhKQljICNDQ0NEQ0QiLAoiYikJYyAjQzRDNEJGIiwKImMpCWMgI0M5RDZEQSIsCiJkKQljICNDQkQ1Q0QiLAoiZSkJYyAjQzJDQUMxIiwKImYpCWMgI0JGQzRDNCIsCiJnKQljICNEN0FFQUUiLAoiaCkJYyAjQ0RBRUFFIiwKImkpCWMgIzE1MTVBMiIsCiJqKQljICNFOEQ1RDQiLAoiaykJYyAjRTVCNkJDIiwKImwpCWMgI0NDQjFDMyIsCiJtKQljICNDQ0I3Q0EiLAoibikJYyAjRENCOEMwIiwKIm8pCWMgI0U3QkFCMiIsCiJwKQljICNFN0JFQUYiLAoicSkJYyAjRjNEMUIyIiwKInIpCWMgI0Y5RDdBRSIsCiJzKQljICNGOENEQUYiLAoidCkJYyAjRjBCM0FCIiwKInUpCWMgI0RBQURBRSIsCiJ2KQljICNCQ0JDQkUiLAoidykJYyAjQzZDMkJFIiwKIngpCWMgI0NFQzZCRCIsCiJ5KQljICNDMUNEQ0IiLAoieikJYyAjQ0JDRUNBIiwKIkEpCWMgI0QxQzhDMiIsCiJCKQljICNCREMwQzEiLAoiQykJYyAjQUZCM0I5IiwKIkQpCWMgI0M3QzZDNyIsCiJFKQljICNDQkNBQzciLAoiRikJYyAjQjhDMUMyIiwKIkcpCWMgI0M2Q0FDNCIsCiJIKQljICNDQ0NEQzciLAoiSSkJYyAjQkZDMkMwIiwKIkopCWMgI0QyQURBRCIsCiJLKQljICNDQUFEQUUiLAoiTCkJYyAjMTYxNUEyIiwKIk0pCWMgIzM5MzlCNiIsCiJOKQljICMwRDBCQTQiLAoiTykJYyAjQUU5N0I5IiwKIlApCWMgIzRFNDVBRCIsCiJRKQljICMxODE1QTUiLAoiUikJYyAjMEQwQUEyIiwKIlMpCWMgIzUzNDVBOCIsCiJUKQljICNFM0M0QjQiLAoiVSkJYyAjRTJDNkFFIiwKIlYpCWMgIzVFNTFBNiIsCiJXKQljICMxRTE3QTMiLAoiWCkJYyAjMTcxMUEyIiwKIlkpCWMgIzRFMzhBNSIsCiJaKQljICNEQjlDQUIiLAoiYCkJYyAjRDg5RUFCIiwKIiAhCWMgIzdENUNBNyIsCiIuIQljICMzRDJEQTQiLAoiKyEJYyAjMUQxNUEyIiwKIkAhCWMgIzBBMDdBMSIsCiIjIQljICMwRTBCQTIiLAoiJCEJYyAjMkMyMUEzIiwKIiUhCWMgIzU2NDJBNSIsCiImIQljICNCNzk2QUMiLAoiKiEJYyAjQjNBQkFDIiwKIj0hCWMgI0IzQjZCQiIsCiItIQljICNDNEM5Q0QiLAoiOyEJYyAjQzNDNUM2IiwKIj4hCWMgI0FFQjJCOSIsCiIsIQljICNCMEI0QkEiLAoiJyEJYyAjQjNCNkI5IiwKIikhCWMgI0FEQURCMCIsCiIhIQljICNBQ0FCQUYiLAoifiEJYyAjOUY5RUIwIiwKInshCWMgIzU0NTRBQSIsCiJdIQljICMyNzI3QTMiLAoiXiEJYyAjMTIxMkEzIiwKIi8hCWMgIzA3MDdBMyIsCiIoIQljICMxQzFEQTQiLAoiXyEJYyAjMzQzM0E1IiwKIjohCWMgIzZFNUJBNyIsCiI8IQljICMyQzIyQTMiLAoiWyEJYyAjQjc4QUE5IiwKIn0hCWMgI0UxQUNBRCIsCiJ8IQljICNDOEFDQUMiLAoiMSEJYyAjQzRDNEU1IiwKIjIhCWMgIzMzMzNCMyIsCiIzIQljICMzMDMwQjIiLAoiNCEJYyAjNTM0OUFBIiwKIjUhCWMgIzI4MjNBNCIsCiI2IQljICMyODFDQTIiLAoiNyEJYyAjRUZBQUFCIiwKIjghCWMgI0M4OTJBQSIsCiI5IQljICMxMTBDQTIiLAoiMCEJYyAjN0U3OEE5IiwKImEhCWMgI0FGQjJCNCIsCiJiIQljICNBREFGQjEiLAoiYyEJYyAjQUJBQkFGIiwKImQhCWMgI0FCQUJCMCIsCiJlIQljICNBQkFDQjAiLAoiZiEJYyAjODU4NUFBIiwKImchCWMgIzA3MDdBMSIsCiJoIQljICMwQjBCQTIiLAoiaSEJYyAjMDgwOEEyIiwKImohCWMgIzc2NTlBNiIsCiJrIQljICNERkFDQUQiLAoibCEJYyAjQzVBQ0FCIiwKIm0hCWMgI0FEQUJBQiIsCiJuIQljICNEQURBRjEiLAoibyEJYyAjMkIyQkIxIiwKInAhCWMgIzA1MDVBMyIsCiJxIQljICMwNzA2QTIiLAoiciEJYyAjNkE1OUFCIiwKInMhCWMgIzg2NzdBQSIsCiJ0IQljICM0MDM3QTciLAoidSEJYyAjM0QzNUE0IiwKInYhCWMgI0E0ODlBQyIsCiJ3IQljICM2RDUyQTYiLAoieCEJYyAjQjU4MUE5IiwKInkhCWMgI0E2NzlBOCIsCiJ6IQljICMwNTAzQTEiLAoiQSEJYyAjNEYzQUE0IiwKIkIhCWMgIzlGNzVBOSIsCiJDIQljICNDNjkzQUIiLAoiRCEJYyAjQzM5MUFBIiwKIkUhCWMgIzkxNkRBOCIsCiJGIQljICMxQTE0QTIiLAoiRyEJYyAjMTQxM0EyIiwKIkghCWMgI0EzQTRBRCIsCiJJIQljICNCMEIzQjYiLAoiSiEJYyAjQUVCMEIyIiwKIkshCWMgI0E3QTdBRiIsCiJMIQljICMzMzM0QTYiLAoiTSEJYyAjOTQ5N0FFIiwKIk4hCWMgI0JDQkFCOSIsCiJPIQljICNDOEM3QzciLAoiUCEJYyAjQTlBQUJDIiwKIlEhCWMgIzYxNUJBNyIsCiJSIQljICMwQTA4QTEiLAoiUyEJYyAjNkQ1M0E3IiwKIlQhCWMgI0RDQURBRCIsCiJVIQljICNDM0FCQUIiLAoiViEJYyAjNkY2RkE4IiwKIlchCWMgI0JGQkZFOCIsCiJYIQljICMxMzEzQTgiLAoiWSEJYyAjOTU5NUQ4IiwKIlohCWMgI0YyRjJGQiIsCiJgIQljICM5QjhBQzIiLAoiIH4JYyAjRERCOUI3IiwKIi5+CWMgI0NDQUZBRCIsCiIrfgljICNCREFDQjAiLAoiQH4JYyAjMTExMEEzIiwKIiN+CWMgIzE5MTZBMyIsCiIkfgljICNFRUQwQUYiLAoiJX4JYyAjRjVDREI0IiwKIiZ+CWMgI0U5QUVBQiIsCiIqfgljICMxRjE2QTIiLAoiPX4JYyAjODE1QkE2IiwKIi1+CWMgI0JCODhBOSIsCiI7fgljICNENzlFQUIiLAoiPn4JYyAjQjg4Q0FCIiwKIix+CWMgIzAyMDFBMSIsCiInfgljICM4Mjg0QjEiLAoiKX4JYyAjQzZDQkNDIiwKIiF+CWMgI0M1QzhDNiIsCiJ+fgljICNCMkI3QkIiLAoie34JYyAjQjlCQUJFIiwKIl1+CWMgIzhDOERCMyIsCiJefgljICNCQ0JFQzgiLAoiL34JYyAjQkZDOEQwIiwKIih+CWMgI0NCQ0JDNCIsCiJffgljICNDNEMzQkIiLAoiOn4JYyAjQkY5QUFEIiwKIjx+CWMgIzdCNUZBNyIsCiJbfgljICNEQUFEQUQiLAoifX4JYyAjNzM3M0FDIiwKInx+CWMgI0UxRTFFMSIsCiIxfgljICM1MTUxQkYiLAoiMn4JYyAjRjVGNUZCIiwKIjN+CWMgI0I2QjNERiIsCiI0fgljICNFOUNCQ0EiLAoiNX4JYyAjREZCMkIxIiwKIjZ+CWMgI0M2QURBRSIsCiI3fgljICMzMzMwQTciLAoiOH4JYyAjNUU1N0E5IiwKIjl+CWMgI0VERDVCNiIsCiIwfgljICNGM0NCQjQiLAoiYX4JYyAjRURCMEFCIiwKImJ+CWMgIzM5MjhBNCIsCiJjfgljICMxRjE4QTMiLAoiZH4JYyAjNjk2QUFEIiwKImV+CWMgI0M3QzdDMCIsCiJmfgljICNDQ0M5QjkiLAoiZ34JYyAjQzNEMUNEIiwKImh+CWMgI0NEQkRCOCIsCiJpfgljICM5Njk4QkQiLAoian4JYyAjQjFBOUJDIiwKImt+CWMgI0JGQzdDRCIsCiJsfgljICNDOEQzQzkiLAoibX4JYyAjQzdDRkM2IiwKIm5+CWMgI0I0QjFCMiIsCiJvfgljICNDRkFFQUUiLAoicH4JYyAjQ0E5QkFBIiwKInF+CWMgIzcwNTZBNiIsCiJyfgljICNDNzlBQUIiLAoic34JYyAjRDdBREFFIiwKInR+CWMgI0JFQUJBQiIsCiJ1fgljICM4MzgzQzAiLAoidn4JYyAjODg4OEQzIiwKInd+CWMgIzAzMDNBMiIsCiJ4fgljICM2RDZEQzkiLAoieX4JYyAjQjZCNkU0IiwKInp+CWMgI0Y2RUFFQSIsCiJBfgljICNFNEJGQkUiLAoiQn4JYyAjRDhBRkFGIiwKIkN+CWMgIzNBMzRBNiIsCiJEfgljICM2NDYxQTciLAoiRX4JYyAjQzNCN0FFIiwKIkZ+CWMgI0UyQkVCMyIsCiJHfgljICNFQ0IwQUMiLAoiSH4JYyAjNEYzOEE1IiwKIkl+CWMgIzVGNDNBNSIsCiJKfgljICNEQTlGQUEiLAoiS34JYyAjNzk1OUE3IiwKIkx+CWMgIzNGMkVBMyIsCiJNfgljICMyMzFBQTIiLAoiTn4JYyAjMTYxMEEyIiwKIk9+CWMgIzMzMjZBMyIsCiJQfgljICM1MjNEQTUiLAoiUX4JYyAjMTgxMkEyIiwKIlJ+CWMgIzU3NTRBOCIsCiJTfgljICNDMkM3QzMiLAoiVH4JYyAjRDBENUM2IiwKIlV+CWMgI0I2QzNDNSIsCiJWfgljICNCRkMyQzYiLAoiV34JYyAjQzhDM0MyIiwKIlh+CWMgI0I0QjRCQyIsCiJZfgljICMwQTBBQTIiLAoiWn4JYyAjMEMwQkEzIiwKImB+CWMgIzQzNDRBQyIsCiIgewljICM1RDVDQUQiLAoiLnsJYyAjNzI2REIxIiwKIit7CWMgIzgxNzNBRCIsCiJAewljICNBNDgzQUIiLAoiI3sJYyAjQzA5NUFCIiwKIiR7CWMgI0RDQUFBQiIsCiIlewljICNEQ0FCQUQiLAoiJnsJYyAjMkMyQ0IwIiwKIip7CWMgIzVFNUVDNCIsCiI9ewljICNCNUI1RTQiLAoiLXsJYyAjRjJFMkUyIiwKIjt7CWMgI0U2QjlCOSIsCiI+ewljICM0MTM0QTYiLAoiLHsJYyAjNzQ2N0FDIiwKIid7CWMgI0MzQUNBRiIsCiIpewljICNEQkFFQUQiLAoiIXsJYyAjRUZBRUFDIiwKIn57CWMgIzU3M0VBNSIsCiJ7ewljICM4NTYxQTciLAoiXXsJYyAjMTIwREExIiwKIl57CWMgIzYxNTVBOSIsCiIvewljICNDQ0M2QzUiLAoiKHsJYyAjQ0JDQ0MwIiwKIl97CWMgI0M1Q0FDOSIsCiI6ewljICNCM0I3QkEiLAoiPHsJYyAjQUJBQ0FGIiwKIlt7CWMgIzgwODBBQiIsCiJ9ewljICMwNjA2QTEiLAoifHsJYyAjMUIxNUEyIiwKIjF7CWMgIzcwNTdBNyIsCiIyewljICNEN0E5QUQiLAoiM3sJYyAjRDNBRUFGIiwKIjR7CWMgIzE3MTdBNCIsCiI1ewljICNEMUQxRUUiLAoiNnsJYyAjRkNGQkZCIiwKIjd7CWMgI0VGRDdENiIsCiI4ewljICM0NjM1QTYiLAoiOXsJYyAjODg2OEFDIiwKIjB7CWMgI0UzQjBCNCIsCiJhewljICNBMjc1QTgiLAoiYnsJYyAjMzgyOUEzIiwKImN7CWMgI0EwNzVBOCIsCiJkewljICNEQUEzQUIiLAoiZXsJYyAjRTFBOUFDIiwKImZ7CWMgI0I2ODhBQiIsCiJnewljICMyNjFEQTMiLAoiaHsJYyAjNkE1NUE4IiwKIml7CWMgI0Q2QjdCNiIsCiJqewljICNEOEMyQkIiLAoia3sJYyAjRDFDOEMwIiwKImx7CWMgI0JFQkFCOSIsCiJtewljICNBRkFCQUUiLAoibnsJYyAjQUZBQkFDIiwKIm97CWMgI0FFQUJBQyIsCiJwewljICM5RjlCQUIiLAoicXsJYyAjNUQ1OUE4IiwKInJ7CWMgIzJDMjlBNSIsCiJzewljICMxQTE2QTMiLAoidHsJYyAjNTA0MEE1IiwKInV7CWMgI0QxQUVBRiIsCiJ2ewljICNCN0FCQUIiLAoid3sJYyAjQURBQ0FDIiwKInh7CWMgIzE4MThBNyIsCiJ5ewljICMwRTBFQTciLAoiensJYyAjQUZBRkUyIiwKIkF7CWMgIzIzMjNBRSIsCiJCewljICMxQjFCQUIiLAoiQ3sJYyAjRTVFNUY1IiwKIkR7CWMgI0ZDRjhGOCIsCiJFewljICM0NjNCQUQiLAoiRnsJYyAjOTA2N0E5IiwKIkd7CWMgI0YwQURBRSIsCiJIewljICM1ODNFQTUiLAoiSXsJYyAjNUU0M0E1IiwKIkp7CWMgIzQ4MzRBNCIsCiJLewljICMzQzJDQTMiLAoiTHsJYyAjRTVBOEFCIiwKIk17CWMgIzNDMkRBNCIsCiJOewljICM2RDU0QTYiLAoiT3sJYyAjRDNBRUIwIiwKIlB7CWMgI0MxQURBRSIsCiJRewljICNDMUFEQUQiLAoiUnsJYyAjQkNBN0FEIiwKIlN7CWMgI0NBQUNBRCIsCiJUewljICNEMUFEQUUiLAoiVXsJYyAjRDdBQ0FDIiwKIlZ7CWMgI0NFQTJBQSIsCiJXewljICNBQTg2QUEiLAoiWHsJYyAjMzcyQ0E0IiwKIll7CWMgI0I3OUNBRSIsCiJaewljICNCNEFCQUIiLAoiYHsJYyAjQzdDNUM2IiwKIiBdCWMgIzE2MTZBOSIsCiIuXQljICMxNTE1QTkiLAoiK10JYyAjM0UzQ0I1IiwKIkBdCWMgIzhENjlBQiIsCiIjXQljICNGNEFDQUIiLAoiJF0JYyAjOEE2NUE3IiwKIiVdCWMgI0Q3QTJBQiIsCiImXQljICMwQzA5QTEiLAoiKl0JYyAjQTc4N0FBIiwKIj1dCWMgIzA1MDRBMSIsCiItXQljICM2QjU1QTYiLAoiO10JYyAjRDhBQ0FDIiwKIj5dCWMgI0Q3QUJBQyIsCiIsXQljICNCMzhFQTkiLAoiJ10JYyAjOEQ3QUFBIiwKIildCWMgI0MwQzFDMCIsCiIhXQljICM4QzhDRDQiLAoifl0JYyAjQzRDNEU5IiwKIntdCWMgIzBBMEFBNSIsCiJdXQljICM0MDQwQjgiLAoiXl0JYyAjODk3QUJGIiwKIi9dCWMgI0VFQjRCMyIsCiIoXQljICM1NjNFQTUiLAoiX10JYyAjNTEzQkE0IiwKIjpdCWMgI0M5OTZBQSIsCiI8XQljICMyRTIzQTMiLAoiW10JYyAjNkQ1M0E2IiwKIn1dCWMgIzg4NjlBOCIsCiJ8XQljICNBRTg5QTkiLAoiMV0JYyAjOUU3RkE5IiwKIjJdCWMgIzlFOEVBQSIsCiIzXQljICNBOEE4REYiLAoiNF0JYyAjNUM1Q0MzIiwKIjVdCWMgI0EyQTJERCIsCiI2XQljICM3ODc2Q0MiLAoiN10JYyAjRjVERURFIiwKIjhdCWMgI0VCQjdCNyIsCiI5XQljICNFREFEQUUiLAoiMF0JYyAjNTgzRkE1IiwKImFdCWMgI0VFQUFBQiIsCiJiXQljICM1RDQ0QTUiLAoiY10JYyAjNDkzNkE0IiwKImRdCWMgIzlCNzJBOSIsCiJlXQljICNBNzdCQTkiLAoiZl0JYyAjODg2NUE4IiwKImddCWMgIzREMzlBNCIsCiJoXQljICMwNDAzQTEiLAoiaV0JYyAjREFBNkFBIiwKImpdCWMgIzg3NjlBOCIsCiJrXQljICMwOTA3QTEiLAoibF0JYyAjNjg1MkE1IiwKIm1dCWMgI0I3OTFBQSIsCiJuXQljICNEMkE5QUIiLAoib10JYyAjOTU3OEE4IiwKInBdCWMgIzE3MTNBMiIsCiJxXQljICMyMDFCQTMiLAoicl0JYyAjQjhBQUFDIiwKInNdCWMgI0VFRUVGOSIsCiJ0XQljICM4Nzg3RDMiLAoidV0JYyAjNzQ3NENDIiwKInZdCWMgI0RFREVGNCIsCiJ3XQljICMyQTJBQjAiLAoieF0JYyAjMDgwOEE0IiwKInldCWMgIzNDM0NCNyIsCiJ6XQljICMxMjEyQTgiLAoiQV0JYyAjRTlFMkVDIiwKIkJdCWMgI0VBQzNDMyIsCiJDXQljICM1QjQ0QTYiLAoiRF0JYyAjMEIwOEExIiwKIkVdCWMgI0JEODhBQiIsCiJGXQljICNEQ0ExQUEiLAoiR10JYyAjMjUxQkEzIiwKIkhdCWMgIzgwNjBBNyIsCiJJXQljICM2QzUyQTYiLAoiSl0JYyAjMkUyNEE0IiwKIktdCWMgIzg5NkNBOCIsCiJMXQljICMwODA3QTIiLAoiTV0JYyAjMTUxMUEyIiwKIk5dCWMgIzEzMEZBMSIsCiJPXQljICNBRTkyQUIiLAoiUF0JYyAjQjdBQkFDIiwKIlFdCWMgI0QwRDBEMSIsCiJSXQljICM4RThFRDUiLAoiU10JYyAjMkMyQ0IxIiwKIlRdCWMgIzNBM0FCNyIsCiJVXQljICNERERERjIiLAoiVl0JYyAjNjg2OEM4IiwKIlddCWMgI0VCRUJGOCIsCiJYXQljICNGQUYyRjIiLAoiWV0JYyAjQTg5NEMyIiwKIlpdCWMgIzEwMENBMiIsCiJgXQljICMxMDBCQTIiLAoiIF4JYyAjQkQ4OUFBIiwKIi5eCWMgI0UyQTVBQiIsCiIrXgljICMzMTI0QTMiLAoiQF4JYyAjMEQwOUExIiwKIiNeCWMgIzJEMjJBMyIsCiIkXgljICM3MTU0QTYiLAoiJV4JYyAjQ0Y5QkFBIiwKIiZeCWMgI0I2ODlBOSIsCiIqXgljICM0NDM0QTQiLAoiPV4JYyAjQkI5M0FBIiwKIi1eCWMgIzE0MTBBMiIsCiI7XgljICM0QTNBQTUiLAoiPl4JYyAjN0Q2M0E3IiwKIixeCWMgIzUzNDFBNSIsCiInXgljICMyODIwQTMiLAoiKV4JYyAjMTIwRkEyIiwKIiFeCWMgIzE4MTNBMyIsCiJ+XgljICMzNDJBQTMiLAoie14JYyAjNzI1REE3IiwKIl1eCWMgI0M3QTRBQyIsCiJeXgljICNDN0FDQUQiLAoiL14JYyAjQzBCNkI2IiwKIiheCWMgI0UzRTNFMyIsCiJfXgljICNCQ0JDRTYiLAoiOl4JYyAjRjZGNkZDIiwKIjxeCWMgIzA2MDZDRiIsCiJbXgljICNGOEVFRUUiLAoifV4JYyAjRUNDOEM4IiwKInxeCWMgI0U3QjBCMiIsCiIxXgljICNFNkFEQUUiLAoiMl4JYyAjREFBRUFEIiwKIjNeCWMgI0RDQUZBRCIsCiI0XgljICNEREFGQUQiLAoiNV4JYyAjRTBBRUFDIiwKIjZeCWMgI0Q0QUNBQiIsCiI3XgljICNDRkFDQUUiLAoiOF4JYyAjQ0NCMkIzIiwKIjleCWMgI0RFRDFEMSIsCiIwXgljICNGOEY3RjciLAoiYV4JYyAjMzMzM0Q3IiwKImJeCWMgI0U4RThGQiIsCiJjXgljICNGQkY3RjgiLAoiZF4JYyAjRUZEOEQ5IiwKImVeCWMgI0RBQjdCOCIsCiJmXgljICNCRkFEQUMiLAoiZ14JYyAjQkVBQ0FDIiwKImheCWMgI0MyQURBRCIsCiJpXgljICNENkFFQUYiLAoial4JYyAjRERBRUFGIiwKImteCWMgI0UwQUNBRSIsCiJsXgljICNEMUFDQUIiLAoibV4JYyAjQ0VBQ0FFIiwKIm5eCWMgI0QyQkJCRCIsCiJvXgljICNFN0RFREUiLAoicF4JYyAjMUUxRUQ0IiwKInFeCWMgI0I4QjhGMSIsCiJyXgljICNGQUY5RjkiLAoic14JYyAjRDdEMENGIiwKInReCWMgI0MyQkZCRSIsCiJ1XgljICNCNkI4QjgiLAoidl4JYyAjQjlCOEJCIiwKIndeCWMgI0JCQjRCNyIsCiJ4XgljICNCOEIyQjIiLAoieV4JYyAjQjRCMUFGIiwKInpeCWMgI0I0QjBBRiIsCiJBXgljICNCQkFFQUUiLAoiQl4JYyAjQ0RCMUIxIiwKIkNeCWMgI0Q2QUZCMCIsCiJEXgljICNEOEFDQUQiLAoiRV4JYyAjRENBQ0FEIiwKIkZeCWMgI0QxQURBRCIsCiJHXgljICNDRUFFQUUiLAoiSF4JYyAjRDJCOUI5IiwKIkleCWMgI0UxRDRENCIsCiJKXgljICNGQkZBRkEiLAoiS14JYyAjRjZGNkZFIiwKIkxeCWMgIzA4MDhDRiIsCiJNXgljICM2NzY3RTIiLAoiTl4JYyAjREZFMkUyIiwKIk9eCWMgI0M5Q0JDRSIsCiJQXgljICNCOUJBQkQiLAoiUV4JYyAjQjlCREJFIiwKIlJeCWMgI0I0QjhCOCIsCiJTXgljICNCOEI5QjkiLAoiVF4JYyAjQkNCQkJDIiwKIlVeCWMgI0JFQjhCQSIsCiJWXgljICNCQ0FGQjIiLAoiV14JYyAjQkJBQkFDIiwKIlheCWMgI0NGQURBRCIsCiJZXgljICNDQ0IxQjEiLAoiWl4JYyAjRDZDM0M0IiwKImBeCWMgI0U0RDlEOSIsCiIgLwljICNGMUVCRUIiLAoiLi8JYyAjQTRBNEVFIiwKIisvCWMgIzIwMjBENSIsCiJALwljICNGMEYyRjIiLAoiIy8JYyAjRDREOEQ5IiwKIiQvCWMgI0NBQ0NDRSIsCiIlLwljICNDQUM5Q0IiLAoiJi8JYyAjQzNDN0M4IiwKIiovCWMgI0JGQzNDNiIsCiI9LwljICNCQUJEQzAiLAoiLS8JYyAjQjRCM0I1IiwKIjsvCWMgI0I5QUVBRiIsCiI+LwljICNENUFGQjAiLAoiLC8JYyAjRDZCNUI1IiwKIicvCWMgI0Q5QkNCQyIsCiIpLwljICNEQkMxQzEiLAoiIS8JYyAjREZDOUM5IiwKIn4vCWMgI0U5RENEQyIsCiJ7LwljICNGNEVERUQiLAoiXS8JYyAjRkJGOUY5IiwKIl4vCWMgIzUwNTBERSIsCiIvLwljICM5MjkyRUEiLAoiKC8JYyAjRUZGMEYwIiwKIl8vCWMgI0U3RThFOCIsCiI6LwljICNFMUUwRTEiLAoiPC8JYyAjREVEQ0REIiwKIlsvCWMgI0UxREJEQyIsCiJ9LwljICNFMUQ5RDkiLAoifC8JYyAjRTNENkQ3IiwKIjEvCWMgI0UzRDNENCIsCiIyLwljICNFN0Q3RDciLAoiMy8JYyAjRThEQ0RDIiwKIjQvCWMgI0VERTVFNiIsCiI1LwljICNGNUYwRjAiLAoiNi8JYyAjRDFEMUY3IiwKIjcvCWMgIzA1MDVDRiIsCiI4LwljICMxOTE5RDMiLAoiOS8JYyAjRUZFRkZDIiwKIjAvCWMgIzNFM0VEQSIsCiJhLwljICM3MzczRTQiLAoiYi8JYyAjNTU1NURFIiwKImMvCWMgIzhBOEFFOCIsCiJkLwljICMwMjAyQ0YiLAoiZS8JYyAjMzYzNkQ4IiwKImYvCWMgI0U1RTVGQiIsCiJnLwljICNGOEY4RkUiLAoiaC8JYyAjRjBGMEZDIiwKImkvCWMgIzNDM0NEOSIsCiJqLwljICM3QTdBRTUiLAoiay8JYyAjOUI5QkVCIiwKImwvCWMgI0I2QjZGMiIsCiJtLwljICNCQUJBRjEiLAoibi8JYyAjQTFBMUVEIiwKIm8vCWMgIzg1ODVFNyIsCiJwLwljICM0QjRCREQiLAoicS8JYyAjMEUwRUQxIiwKIiAgICAgICAgICAgICAgICAgICAgICAgIC4gKyArICsgKyArICsgKyArICsgKyArICsgKyArICsgKyArICsgKyArICsgKyArICsgKyArICsgKyArICsgKyArICsgKyArICsgKyArICsgKyArICsgKyArICsgKyArICsgKyArICsgKyArICsgKyArICsgKyArICsgKyArICsgICAgICAgICAgICAgICAgICAgICAgICAgIiwKIiAgICAgICAgICAgICAgICAgIC4gKyArICsgKyArICsgKyArICsgKyArICsgKyArICsgKyArICsgKyArICsgKyArICsgKyArICsgKyArICsgKyArICsgKyArICsgKyArICsgKyArICsgKyArICsgKyArICsgKyArICsgKyArICsgKyArICsgKyArICsgKyArICsgKyArICsgKyArICsgICAgICAgICAgICAgICAgICAgIiwKIiAgICAgICAgICAgICAgLiArICsgKyArICsgKyArICsgKyArICsgKyArICsgKyArICsgKyArICsgKyArICsgKyArICsgKyArICsgKyArICsgKyArICsgKyArICsgKyArICsgKyArICsgKyArICsgKyArICsgKyArICsgKyArICsgKyArICsgKyArICsgKyArICsgKyArICsgKyArICsgKyArICAgICAgICAgICAgICAgIiwKIiAgICAgICAgICAgICsgKyArICsgQCAjICQgJSAmICogKiAqICogKiAqICogKiAqICogKiAqICogKiAqICogKiAqICogKiAqICogKiAqICogKiAqICogKiAqICogKiAqICogKiAqICogKiAqICogKiAqICogKiAqICogKiAqICogKiAqICogKiAqICogKiAqICogKiA9IC0gOyA+ICwgKyArICsgKyAgICAgICAgICAgIiwKIiAgICAgICAgJyArICsgKyApICEgfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IHsgXSArICsgKyAnICAgICAgICAgIiwKIiAgICAgICAgKyArICsgXiAvIH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiAoIF8gKyArICsgICAgICAgIiwKIiAgICAgICsgKyArIDogfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IDwgWyArICsgICAgICAgIiwKIiAgICArICsgKyB9IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfCAsICsgKyAgICAgIiwKIiAgICArICsgMSAyIH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiBeICsgKyAuICAgIiwKIiAgKyArICsgMyB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IDQgNSA2IDcgOCA5IDAgYSBiIGMgZCBlIGYgZyBoIGkgaiBrIGwgbSA0IG4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiBvIHAgKyArICAgIiwKIiAgKyArIHEgfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gciBzIHQgdSB2IHcgeCB5IHogQSBCIEMgRCBFIEYgRyBIIEkgSiBLIEwgTSBOIE8gUCByIH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IFEgKyArICAgIiwKIiAgKyArIFIgfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IG4gUyBUIFUgViBXIFggWSBaIGAgIC4uLisuQC4jLiQuJS4mLiouSCA9Li0uOy4+LiwuJy4pLiEufi57Ll0uciB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IF4uKyArIC4gIiwKIisgKyArIC8ufiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiA0ICguXy46LjwuWy59LnwuMS4yLjMuNC41LjYuNy44LjkuMC5hLmIuYy5kLmUuZi5nLmguaS5qLmsubC5tLm4uby5wLn4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IHEuci4rICsgIiwKIisgKyArIHMufiB+IH4gfiB0LnUudi52LnYudi52LnYudi52LnYudi52LnYudi52LnYudi53LnguMS4xLnkuei5BLkIuQy5ELnYudi52LnYudi52LnYudi52LnYudi52LnYuRS5GLkcuRy5ILkkuSi5LLkwudi52LnYudi52LnYudi52LnYudi52LnYudi52LnYudi5NLk4ufiB+IH4gfiB+IH4gfiB+IH4gTy4rICsgIiwKIisgKyBQLn4gfiB+IH4gfiBRLnYudi52LnYudi52LnYudi52LnYudi52LnYudi52LnYudi52LlIuUy5TLlQuQS5VLlYudi52LnYudi52LnYudi52LnYudi52LnYudi52LnYudi5XLlguWS5YLlouYC52LnYudi52LnYudi52LnYudi52LnYudi52LnYudi52LnYudi52LiArfiB+IH4gfiB+IH4gfiB+IH4gLisrICsgIiwKIisgKyArK34gfiB+IH4gfiB1LnYuQCsjKyMrIysjKyMrJCt2LnYuJCslKyYrKis9Ky0rOyt2LnYuPissKycrKSshK34reytdK14rXiteK14rLyt2LnYuKCtfK18rOis6KzwrWyt9K3wrfCt8KzErMiszKzQrNSs2K3Yudi43KyMrIysjKyMrIysjKyMrIysjKyMrOCt2LjkrfiB+IH4gfiB+IH4gfiB+IH4gMCsrICsgIiwKIisgKyArK34gfiB+IH4gfiBhK3YuYit+IH4gfiB+IH4gYyt2LnYuZCtlK2YrZytoKycraSt2LnYuaitBLmsrIStsK20rbitvK3ArcStyK3MrdCt2LnYudSt2K3creCt5K3orQStCK0MrRCtFK0YrRytIK0krSitLK3Yudi5MK34gfiB+IH4gfiB+IH4gfiB+IH4gTSt2LjkrfiB+IH4gfiB+IH4gfiB+IH4gMCsrICsgIiwKIisgKyArK34gfiB+IH4gTit2LnYuTyt+IH4gfiB+IH4gUCt2LnYuUStSK0EuUyspKykrVCt2LnYuVStrK2wrbStwK1YrVytXK3ErcitYK1krWit2LnYuYCtHLiBAIEAuQEErK0BAQCNAJEAlQCZAKkA9QC1AO0A+QHYudi4sQH4gfiB+IH4gfiB+IH4gfiB+IH4gTSt2LjkrfiB+IH4gfiB+IH4gfiB+IH4gMCsrICsgIiwKIisgKyArK34gfiB+IH4gJ0B2LnYuKUB+IH4gfiB+IG4gIUB2LnYufkB7QGwrIStrKykrXUB2LnYuXkAvQG0rcCtwK1YrVysoQHMrcytzK19AOkB2LnYuYCs8QFtAfUB8QDFAMkAzQDRANUA2QDdAN0A2QDhAOUAwQHYudi5hQGJAfiB+IH4gfiB+IH4gfiB+IH4gTSt2LjkrfiB+IH4gfiB+IH4gfiB+IH4gMCsrICsgIiwKIisgKyArK34gfiB+IH4gY0B2LnYuZEB+IH4gfiBlQGZAZ0B2LnYuaEBpQGwrbCshKyErakB2LnYua0BsQG4rbSttK21AbkBxK29AcEBwQHFAckB2LnYuYCsgQHNAdEB1QDJAdkB3QHhAeUB6QEFAQkBBQENAREBFQHYudi5GQEdASEB+IH4gSUBKQEtAfiB+IH4gTEB2Lk1AfiB+IH4gfiB+IH4gfiB+IH4gMCsrICsgIiwKIisgKyArK34gfiB+IH4gTkB2LnYuT0B+IH4gfiBQQFFAUkB2LnYuU0BvK1RAbEBsQGwrVUB2LnYuVkBXQFRAWEBwK3ErbkBZQGguX0BaQGBAckB2LnYuYCsgQHNAICMuI3ZAd0ArI0AjIyMkIyUjJiMqIz0jLSM7I3Yudi4+IywjJyMpI34gISN2Lk0rSUB+IH4gfiN7I10jfiB+IH4gfiB+IH4gfiB+IH4gMCsrICsgIiwKIisgKyArK34gfiB+IH4gXiN2LnYuLyN+IH4gNiAoI18jOiN2LnYuPCNyK1crbitsQCErWyN2LnYufSNXK1crV0B8I28rMSNZQFkrMiNxQDMjOkB2LnYuYCs0I3RAdUA1IzYjNyNAIyMjJCMmIzgjOSMwI2EjYiNjI3Yudi5kI2UjZiNnI2gjaSN2LnYuaiN+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gMCsrICsgIiwKIisgKyArK34gfiB+IH4gSUBMQHYuTi5+IGsjbCNtI24jbyN2LnYuU0BwKyhAcStwK2wrcCNMLnEjciNzI3QjdSN2I3cjeCN5I3ojbUBwQFpAOkB2LnYuQSNzQEIjQyN2QEQjRSMjIyUjRiNHI0gjSSNKI0sjTCNNI3Yudi5OI08jUCNQI1EjUiN2LnYuaiN+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gMCsrICsgIiwKIisgKyArK34gfiB+IH4gfiAyIFMjfiB+IFQjVSNWI1cjWCN2LnYuPCNyK3IrcitxK20rbEBZI1ojYCMgJC4kKyRAJCMkJCQlJCYkKiQ9JGkuckB2LnYuLSRzQDskPiR2QCwkQCMnJCkkOCMhJH4keyRdJF4kLyQoJHYudi52LnYudi52LnYudi52LnYuaiN+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gMCsrICsgIiwKIisgKyArK34gfiB+IH4gfiB+IH4gfiBfJDokPCRbJH0kfCR2LnYuMSRzK3IrcitxK1YrVEAyJDMkNCQ1JDYkNyQ4JDkkMCRhJGIkYy5jJGQkZSR2LnYuZiRzQGckPiRoJDcjaSRqJEYjayRsJG0kbiRvJHAkcSRyJHYudi5zJHQkdSR2JHckeCR2LnYuaiN+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gMCsrICsgIiwKIisgKyArK34gfiB+IH4gfiB+IH4gbiB5JHokQSRCJEMkRCR2LnYuMSRzK3IrcitxK1YrRSRGJEckSCRJJEokSyRMJE0kTiRPJFAkUSRgIFIkUyR2LnYuVCRVJGckPiRoJFYkVyRYJFkkMCNaJGAkICUuJSslQCUjJXYudi4kJSUlJiUqJT0lLSV2LnYuaiN+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gMCsrICsgIiwKIisgKyArK34gfiB+IH4gfiB+IHIgOyU+JSwlJyUpJSElfiV2LnYuMSQyI3MrWCtyK3wjeyVdJV4lLyUoJV8lOiU8JVslfSV8JTAkLyUxJTIlMyV2LnYuZiRVJDQlPiRoJFYkVyQlIzUlSCM2JTclOCU5JTAlYSViJXYudi5jJWQlZSVmJU0kZyV2Lk0uaCV+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gMCsrICsgIiwKIisgKyArK34gfiB+IH4gfiB+IGklaiVrJWwlbSVuJUkgbyV2LnYuMSQyI1krcytyK3AlZS5xJT0uciVzJXQlcyVzJXUlLCMsI3YlWyV3JXgleSV2LnYueiVVJDQlPiRBJUIlVyQlIzUlSCNDJUQlOCVFJUYlRyVIJXYudi5JJUolSyVMJU4kTSVOJU8lfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gMCsrICsgIiwKIisgKyArK34gfiB+IH4gfiB+IFAlUSVSJVMlVCVVJVYlVyV2LnYudStfQDIjWSsoQFglWSVaJWAlICYuJi8lcyV9JSwjKyYrJkAmfSUjJiQmJSZ2LnYuYCtzQCYmKiZBJUIlPSYlIzUlISRDJUQlLSY7Jj4mLCYnJnYudi4pJiEmfiZ7Jl0mTCReJi8mKCZ+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gMCsrICsgIiwKIisgKyArK34gfiB+IH4gfiBuIF8mOiY8JlsmfSZ8JjEmMiZ2LnYudStxQHFAWStvKzMmNCY1JjYmNyY4JjkmdSV1JTAmYSZiJmMmLCNkJkIkZSZ2LnYuLSRzQEIjKiZBJWYmZyZYJFkkMCNoJmkmOCU7Jj4mLCZqJnYudi5rJmwmbSZuJm8mcCYwJD0lcSZ+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gMCsrICsgIiwKIisgKyArK34gfiB+IH4gfiByJnMmdCZ1JnYmdyZ4JjsueSZ2LnYudStxQHFAeiZBJkImQyZgJUQmRSZGJkcmSCZJJkomSyZMJk0mTiZPJlAmUSZ2LnYuZiRSJkIjUyZUJlUmViZqJCojVyZ+JFgmWSY5JUYlWiZqJnYudi5gJiAqLiorKkAqIyokKl4mIyplQH4gfiB+IH4gfiB+IH4gfiB+IG4gJSp+IH4gMCsrICsgIiwKIisgKyArK34gfiB+IH4gciAmKioqPSotKjsqPiosKicqKSp2LnYuYCtgQHFAai4hKm4jfio4JHwlYCV7Kl0qXiovKigqTyRfKjoqPCpPJlsqZSZ2LnYuZiRSJkIjNCVUJn0qfCoxKjIqMyo0KjUqNio3KjgqOSonJnYudi4wKmEqYipjKmQqXSZlKl4mLyUlKn4gfiB+IH4gfiB+IH4gfiBmKmcqaCppKn4gMCsrICsgIiwKIisgKyArK34gfiB+IH4gaiprKmwqbSpuKm8qcCpxKmQkcip2LnYuYCt3K3FAcUBzKnQqRSYsIywjdSplKnYqdyp4KkskeSp6KkEqfSU9LkIqQyp2LnYuYCs0I3NAJiY+JGgkRCpFKkYqNSUhJGgmRypIKislSSpKKnYudi5LKkwqTSpOKk8qUCpOJC8lMCZRKn4gfiB+IH4gfiB+IH4gUiowJnAmUypUKn4gMCsrICsgIiwKIisgKyArK34gfiB+IH4gNiBVKlYqVypYKlkqWipgKiA9Lj12LnYuKz1APUA9QD0jPSQ9JT1zJSY9Kj09PSY9dSp7Ki09Oz0+PSw9Jz0pPSE9fj12LnYuez1dPV09Xj0vPSg9Xz06PTw9Wz1rJH09fD0xPTI9Mz00PXYudi45KzU9Nj03PTg9OT0vJjAkMCYwPX4gfiB+IH4gfiBlQGE9JCowJj0lcCZmJX4gMCsrICsgIiwKIisgKyArK34gfiB+IH4gYj1jPWQ9ZT1mPXYudi52LnYudi52LnYudi52LnYudi52Lmc9aD1pPWo9az1bJTAmLCNPJmw9di52LnYudi52LnYudi52LnYudi52LnYudi52LnYudi5tPW49bz04I0gjcD12LnYudi52LnYudi52LnYudi52LnYudi5xPXI9XiZmJWVAfiB+IHM9UypwJjAmMCQwJF4mMCR0PX4gMCsrICsgIiwKIisgKyArK34gfiB+IH4gdT12PXc9eD15PXo9di52LnYudi52LnYudi52LnYudi5BPUI9Qz1EPTAmRT1JJiwjLCNGPUc9SD1MLnYudi52LnYudi52LnYudi52LnYudi52Lkk9Sj1LPUw9TT1OPTMqTz1QPUwudi52LnYudi52LnYudi52LkwuUT1SPTwlXiZTPSgmVD1SKjA9PSVeJlAqTipOKmE9TiolKn4gMCsrICsgIiwKIisgKyArK34gfiB+IH4gVT1WPVc9WD1ZPVk9Wj1gPVkuIC1YLi4tKy08QEcuditxQEAtRSQjLWAgJC0lLXwlMCYmLT0lXiYqLT0tLS07LXwjKEByK1crPi1fQCwtJy0pLSEtfi17LV0tXi0vLSgtXy06LTwtWy19LXwtMS1jKjEtMi0zLTQtUCo1LTwlXiYvJUAqUCpOJEwkTCU2LWVAfiB+IH4gfiB+IH4gMCsrICsgIiwKIisgKyArK34gfiB+IH4gNy04LTktMC1hLWItYy1kLWQtZS0gLSstZi1nLWgtaS1pLWBAcEBqLWstbC1tLS0ubi1vLXAtcS1yLXMtdC0vQGlAbCt1LVYrVitXK3Ytdi13LXgteS16LUEtQi1DLUQtRS1GLUctSC1JLUotdD1LLUstTC00LVQqTS1TPTwlXiZ1JSMqIypoKk4qbiB+IH4gfiB+IH4gfiB+IH4gMCsrICsgIiwKIisgKyArK34gfiB+IH4gTi1PLVAtUS1SLVMtVC1kLWQtZS1VLVYtZi1nLVctMyNgQHcrQC1YLVktWi1gLSA7LjsuOys7Zi5AOyM7ZytnKyQ7JTsmOycrKjspKz07LTs7Oz47LDsnOyk7ITt+O3s7XTteOy87KDtfOzo7Zyo8Ozw7ZypvJkwlIypOJDwlXiZ1JVs7fTtlQH4gfiB+IH4gfiB+IH4gfiB+IH4gMCsrICsgIiwKIisgKyArK34gfiB+IH4gfDtPLTE7MjtXPVMtMztkLTQ7WS4uLSBAeCtXLXcrLC01O2guPi0+LShAbyt5IzY7Nzs4Ozk7MDthO2I7YztkO2U7ZTtlO2Y7ZztoO2k7eCNqOzstWi1rO2w7bTtuO287cDtxO3I7czt0O3U7djt3OzA9JyMwPXg7LyZbO3I9XiYwJkwtbiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gMCsrICsgIiwKIisgKyArK34gfiB+IH4geTt6O1YtPEBpLWgtZy1oLTIjWStZK3IrcStwK3ArbStsKyErIStrKykrKjsqOycrJysmOyY7QTtCO0M7RDtFO0Y7RztGO0g7RTtFO0U7STtKO0s7TDtNO047TztQO1E7UjtTO1Q7VTtWO1c7WDtZO1M9WjsvJlM9cCZMJC8lMCYwJlIqbiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gMCsrICsgIiwKIisgKyArK34gfiB+IH4gYDsgPi4+Lj4rPkA+Iz4kPiU+Jj4qPj0+LT47PmcuPj50Iyw+LD4nPic+KT4pPiM7IzshPn4+ez5oO10+Xj4vPig+Xz4vPjo+PD5bPn0+fD5KO0w7MT4yPng9Mz40PjMkUDtRO18jNT42Pjc+Xyo4Pls7OT5wJls7TSQ8JT0lMCZ1JVMqbiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gMCsrICsgIiwKIisgKyArK34gfiB+IH4gMD5hPmI+Yz5QLWQ+ZT5mPmc+MSt5K2g+aT5SJiBAaj5rPiwtQC1oLj4tdi12LWw+bT5tPm4+LTtnKzEubz5MO3A+cT5KO0w7SztyPnM+cz50PnU+dj52I2Y7dz54PkA7eT56PkE+Qj5DPkMmRD5FPk0kTSRNJEwkPCUwJF4mMCYwJkY+fiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gMCsrICsgIiwKIisgKyArK34gfiB+IH4gTi1HPkg+ST5KPko+US0zOzktSz5lLWUtIC1MPkw+PEBHLkcudiszI1pAX0BwQG9Ab0AoQHArbCtrK00+Uy5OPkM7QztOPmU7ZDtCO08+Tz58LlA+fC5RPlI+Uz4jO1Q+VT5WPlc+WD5ZPlo+YD4gLCAsLiwkKjwlcj0vJV4mMCZ1JVIqfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gMCsrICsgIiwKIisgKyArK34gfiB+IH4gKyxALCMsST5JPiQsMC0lLGMtYD1gPSYsIC1MPistPEBHLmgtditgQDIjWStzK3MrcityK3ErbSshK2grTT56LiU7KiwlOz0sLSw7LCY7JjsqOz4sdSMsLCcsKSwhLGcufix7LHo7XSxeLC8sKCxyJXIlXyw8JXI9LyU9JTAmdSUwJk8qaCN+IH4gfiB+IH4gfiB+IH4gfiB+IH4gMCsrICsgIiwKIisgKyArK34gfiB+IH4gOiw8LFssfSx8LDEsMixnPlQtYD1ZPSAtIC1MPkw+Zy1nLWgtaS1xQDIjWStzK3IrcityK3IrVEBsQC9AISszLDQsPiwpK2srPTs1LCc+Niw3LHtAbj5zI3ArKEA4LDksMCx4LSktYSxiLDQmcj1jJmMmcj0wJC8lPSVeJjAmdSVeJl0mMS1jLCkjfiB+IH4gSEBTKmQsZSx+IH4gMCsrICsgIiwKIisgKyArK34gfiB+IH4gZixnLGgsaSxqLGssWCBsLEIjbSxlLVkubixYListZi1nLWgtaS1gQHFAWStZK3MrcityK3IrVEBvLGlAbCtWK2xAaUBwLHEscixzLHQsdSx2LHMsdyx4LD4tWCt5LHosQSxCLEMsRCxFLEYsMCQwJEcsLyUvJT0lXiYwJnUlMCY9JVM9NS0wPTA9byZRKkwtWztwJjQtMy1lQH4gMCsrICsgIiwKIisgKyArK34gfiB+IH4gSCxJLEosSyxMLE0sTixPLFAsUSxtLGUtVS1ZListZi1nLWgtaS1gQHFAMiNZK3MrcytyK3ArUixvLG0rcCtwK28rMDtTLFQsVSxWLGAgYCBXLFgsWSxaLGAsISogJy4nLC0rJ0AnIyckJyUnJicqJz0lPSVeJl4mMCZzJXUlfSVwJigmfiB+IGkqTC1dJmUqPSVyPWcqeDs9J34gMCsrICsgIiwKIisgKyArK34gfiB+IH4gLSc7Jz4nLCcnJyknISd+J3snXSdeJ2UtJiwgLUw+Zi1nLWgtaS1gQHFAMiNZK1krcytyK1lAbj5sQHArcStwLC8nKCdfJzonPCdbJ2k9fSdbJ3wnMScyJzMnNCc1J2guLidALXcrNic3JzgnOScwJ2Endi52LmInYyd9JXUlfSV3O34gfiB+IH4gfiBkJ0wtLyV1JV4mUz1zPX4gMCsrICsgIiwKIisgKyArK34gfiB+IH4gZSdmJ2cnaCdpJ2onaydsJ20nbidvJ3AnZS1VLVguKy0rLWgtaC1gQHFAcUBZK1krWStZK29AcCtwK3ArVitxJ3Incyd0J3Undid3J3QldCV4J3kneidBJ0InQydEJ20+Pi1YK2ouaC5FJ0YnRydIJ0kndi52LnYuSid1JXUlfSVkLH4gfiB+IH4gfiB+IH4gdD1NJHAmTiplQH4gMCsrICsgIiwKIisgKyArK34gfiB+IH4gbiBLJ0wnTSdOJ08nUCdRJ1InUydUJ1UnMismLEw+TD5mLWctaC1pLWBAcUAyI1krcytzK1krcCtzI20rVidXJ1gnWSdaJ2AnICkuKSspQCkjKSQpJSkmKSopPSktKTUsKEA7KXMrWC0+KSwpRydqPScpKSkhKXYufil1JXUlcj1UPX4gfiB+IH4gfiB+IH4gZUAgKigmfiB+IH4gMCsrICsgIiwKIisgKyArK34gfiB+IH4gfiB7KV0pXikvKSgpXyk6KTwpWyl9KXwpMSkmLHkrTD5mLWctaS1pLWBAcUAyI1krcytyKyhAcCttK2wrMDsyKTMpNCk1KTYpNyk4KTkpMClhKWIpYylkKWUpZilgIGcpVytZQHMrVitoKSwpJj1qPSY9fSVpKXYufil1JXUlQCpuIH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gMCsrICsgIiwKIisgKyArK34gfiB+IH4gfiB+IGopaylsKW0pbilvKXApcSlyKXMpdClZLlguTD5mLWctaS12K2BAcUAyI1krcysoQFcrVitzI3tAdSlXLHYpdyl4KXkpeilBKUIpQylEKUUpRilHKUgpSSlEPUopWEBsK3ArbEBLKTEldSUmPXUlfSVMKXYufil1JS8lMS1+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gMCsrICsgIiwKIisgKyArK34gfiB+IH4gTSl2LnYuTilPKVApUSlSKVMpVClVKVYpVylYKVkpWilmLWctaS12K2BAcUBgKSAhLiErIUAhIyEkISUhJiEqIT0hLSE7IT4hLCEnISkhISF+IXshXSFeIS8hKCFfITohaEA8IVshfSF8ITEldSUmPXUlfSVpKXYufil1JTUtMSE3K3Yudi52LnYuMiF+IH4gfiB+IH4gfiB+IH4gMCsrICsgIiwKIisgKyArK34gfiB+IH4gMyF2LnYudi56PXYudi52LnYuNCE1IXYudi52LnYuNiE3IWctaC1pLWBAOCE5IXYudi52LnYudi52LnYuOyswIU0lYSFiIWMhZCFlIU0lZiFnIXYudi5oIWkhdi52LnYudi52LmohayFsIW0hdSUmPXUlfSVMKXYufikwJlMqbiFiK3Yudi52LmErbyF+IH4gfiB+IH4gfiB+IH4gMCsrICsgIiwKIisgKyArK34gfiB+IH4gfiBqI3Ahdi5xIXIhcyF0IXYudi52LnUhdiF3IXYudi54IWctaC1pLWBAeSF2LnohQSFCIUMhRCFFIUYhdi5HIUghSSFKIWMhYyFjIUshYSd2LkwhTSFOIU8hUCFRIVIhdi52LlMhVCFVIW0hdSUmPXUldSVpKXYuViF4O2VAVyFYIXYuIytZIVohfiB+IH4gfiB+IH4gfiB+IH4gMCsrICsgIiwKIisgKyArK34gfiB+IH4gfiB+IHAhdi5gISB+Ln4rfkB+di4jfiR+JX4mfip+di49fmctaC1pLWBAcUAtfjt+WStyK3ErVitWKz5+LH52Lid+KX4hfn5+e34mJV1+di5AK15+L34ofl9+TiFKKzp+Vyl2Ljx+W35kLm0hdSUmPXUldSVpKXYufX58fktATS52LjF+Mn5+IH4gfiB+IH4gfiB+IH4gfiB+IH4gMCsrICsgIiwKIisgKyArK34gfiB+IH4gfiB+IHAhdi4zfjR+NX42fjd+di44fjl+MH5hfmJ+di5UJGctaC1pLWBAcUBxQDIjWStvQChAKEB1LVdAY352LmR+ZX5mfmd+RSlofml+di44K2p+a35sfm1+bn5vfiM7cH5xfnJ+c350fm0hdSV1JXUldSVpKXYudX52fnd+di54fn4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gMCsrICsgIiwKIisgKyArK34gfiB+IH4gfiB+IHAhdi55fnp+QX5CfkN+di5EfkV+Rn5Hfkh+di5JfmctaC1pLWBAcUBKfkt+TH5NfkE9Tn5PflB+UX52LlJ+U35UflV+Vn5Xflh+WX52Llp+YH4gey57K3tAeyN7JHs7LCV7dyMyJW0hdSV1JXUldSVpKXYuJnt2LnYuKnt+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gMCsrICsgIiwKIisgKyArK34gfiB+IH4gfiB+IHAhdi49e34gLXs7ez57di4seyd7KXshe357di5JfmctaC1pLWBAe3tAIXYudi52LkE9XXssfnYudi52Ll57L3soe197Ons8e2MhW3t9e3Yudi52LnYudi52LnYufHsxezJ7M3tsLX0ldSV1JXUldSU0e3Yudi52LnYuJCs1e34gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gMCsrICsgIiwKIisgKyArK34gfiB+IH4gfiB+IHAhdi49e34gNns3ezh7di45ezB7KS1wJ357di5JfmctaC1pLWF7di52LmJ7Y3tke3ArbkBle2Z7Z3t2Lmh7aXtqe2t7bHtte257b3twe3F7cntzezsrdi52LnYudi52LnR7dXt2e30ldSV1JXUld3t4e3YueXt6e0F7di5Ce0N7fiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gMCsrICsgIiwKIisgKyArK34gfiB+IH4gfiB+IHAhdi49e34gfiBEe0V7di5Ge0d7MStlLUh7di5Je3graC12K0p7di5Le0x7cytZQFlAVytXQG8sTXt2Lk57dSNmK097Nn5Qe1F7UntTe1R7dyNVe2c7Tz5We1d7WHt2LnYuWXtae3wldyV8JXd7YHsgXXYuTi5+IFMjLl12Lm8hMn5+IH4gfiB+IH4gfiB+IH4gfiB+IH4gMCsrICsgIiwKIisgKyArK34gfiB+IH4gfiB+IHAhdi49e34gfiB+ICtddi5AXXkrI10mLH57di5Je0cuaS1oLU5+di4kXXBAcytyK3ErcitxKyVdJl12LlMhPixBLmYreyU0PipdPV0tXTtdQjtCO0I7ZDtkOz5dLF12LnYuJ11EPTAmfSV8JSldZCcgXXYuIV1+IH4gfl17XXYuXV1oJX4gfiB+IH4gfiB+IH4gfiB+IH4gMCsrICsgIiwKIisgKyArK34gfiB+IH4gfiB+IHAhdi49e34gfiB+IE0pdi5eXS9dWi5aLihddi5Je2gtaS1oLS49di5fXXBAWSsoQFcrcis6XTxddi52LltdPiwpKycrJjsmO31ddi53LnxdQjtPPmQ7Pl1lO0M7MV12LnYuMl0xJSY9XiYpXX4gfiAgXXYuIV1+IH4gfiAzXXd+di40XX4gfiB+IH4gfiB+IH4gfiB+IH4gMCsrICsgIiwKIisgKyArK34gfiB+IH4gfiAyfnAhdi41XUlAfiB+IE0pdi42XTddOF05XShddi4wXWFdaS0zI2Jddi52LmNdZF1lXWZdZ11oXXYuUi52LmhAaV0pKyo7KjsnK2pddi52LmtdbF1tXU8+dT5uXW9dcF12LnFdcl11JUcnbyZkJ34gc10uXXYuIV1+IH4gfiB+IHRddi52LnVddl1OK34gfiB+IH4gfiB+IH4gMCsrICsgIiwKIisgKyArK34gfiB+IH4gd11hK3Yudi52LnhdbiF+IHlddi52LnpdQV1CXUNddi52LkRdRV1aQEZdR112LnYudi52LnYudi53LkhdSV12LnYuTC5KXSY7JDssK0tddi52LnYudi52LkxdTV1JJ3Yudi5OXU9dUF1yJVFdfiAzXU0udi52LnYuUl1+IH4gfiBJQFNddi52LnYudi54XXZdfiB+IH4gfiB+IH4gMCsrICsgIiwKIisgKyArK34gfiB+IH4gVF12LnYudi52LjcrVV1+IFZdTC52Li5dV11YXVldWl12LmBdIF4zIzIjLl5LfiteQF5JPSNeJF4lXm0rJl4mXXYuTC4qXiY7eS5BOz1eLV47Xj5eLF4nXilePV0hXn5ee15dXl5eL14oXmgjfiBfXjYrdi52Lk0rNXt+IH4gfiA6Xjkrdi52LnYudi5MQGojfiB+IH4gfiB+IH4gMCsrICsgIiwKIisgKyA8Xn4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gW159XnxeMV4jO1t+W34yXjNeNF41Xm4+VitwK2wraytTKz4sKSspKycreS55LnkuQTsxLkI7Tj50PnI+Nl5LO0Q7N144XjleMF5+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gYV4rICsgIiwKIisgKyArIGJefiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiBjXmReZV5kLmZeOy5nXmheO0ArO2leal5rXlMrUytoK2grZysnKyY7JjtBO0E7MS5PPk4+dT51PnQ+SztsXm1ebl5vXjZ7fiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gcF4rICsgIiwKIisgKyArIHFefiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gcl5zXnRedV52XndeeF55XnpeQV5CXkNeRF5FXnouei4sK3ouJTtQPkI7Tz5OPnQ+Nl4xPkZeR15IXkleSl5+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IEteTF4rICsgIiwKIiAgKyArIE1efiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+ID0nTl5PXlBeUV5SXlNeVF5VXlZeV14jLXcjez5BO3kuQTtCO0I7Tj50PmAtWF5ZXlpeYF4gL3IgfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IC4vKyArICsgIiwKIiAgKyArICsvaCV+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiBuIEAvIy8kLyUvJi8qLz0vLS87Ly0tUiRXJ2YuPi8sLycvKS8hL34vey9dL3IgbiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IF4vKyArICAgIiwKIiAgKyArICsgLy9+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gKC9fLzovPC9bL30vfC8xLzIvMy80LzUvSl5+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiA2LzcvKyArICAgIiwKIiAgICArICsgOC85L34gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gNCA0IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiAwKysgKyAuICAgIiwKIiAgICAnICsgKyAwL3EufiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gYS8rICsgKyAgICAgIiwKIiAgICAgICsgKyArIGIvMiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IGMvZC8rICsgICAgICAgIiwKIiAgICAgICAgKyArICsgZS9mL34gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gZy9RICsgKyArICsgICAgICAgIiwKIiAgICAgICAgICArICsgKyByLlIgaC9+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiB+IH4gfiAyIC8vOC8rICsgKyArICAgICAgICAgIiwKIiAgICAgICAgICAgICsgKyArICsgWyBpL2ovay9sL20vbS9tL20vbS9tL20vbS9tL20vbS9tL20vbS9tL20vbS9tL20vbS9tL20vbS9tL20vbS9tL20vbS9tL20vbS9tL20vbS9tL20vbS9tL20vbS9tL20vbS9tL20vbS9tL20vbS9tL20vbS9tL20vbS9tL20vbS9uL28vcC9xLysgKyArICsgICAgICAgICAgICAgIiwKIiAgICAgICAgICAgICAgLiArICsgKyArICsgKyArICsgKyArICsgKyArICsgKyArICsgKyArICsgKyArICsgKyArICsgKyArICsgKyArICsgKyArICsgKyArICsgKyArICsgKyArICsgKyArICsgKyArICsgKyArICsgKyArICsgKyArICsgKyArICsgKyArICsgKyArICsgKyArICsgKyArICAgICAgICAgICAgICAgIiwKIiAgICAgICAgICAgICAgICAgIC4gKyArICsgKyArICsgKyArICsgKyArICsgKyArICsgKyArICsgKyArICsgKyArICsgKyArICsgKyArICsgKyArICsgKyArICsgKyArICsgKyArICsgKyArICsgKyArICsgKyArICsgKyArICsgKyArICsgKyArICsgKyArICsgKyArICsgKyArICsgICAgICAgICAgICAgICAgICAgIiwKIiAgICAgICAgICAgICAgICAgICAgICAgICAgKyArICsgKyArICsgKyArICsgKyArICsgKyArICsgKyArICsgKyArICsgKyArICsgKyArICsgKyArICsgKyArICsgKyArICsgKyArICsgKyArICsgKyArICsgKyArICsgKyArICsgKyArICsgKyArICsgKyArICsgKyArICAgICAgICAgICAgICAgICAgICAgICAgICAgIn07Cg=="


#################################################################
#
# Main subroutines
#
#################################################################

# Prepare to plot...
app = PyQt5.QtWidgets.QApplication(sys.argv)	
form = clearMaskGui()
app.exec_()

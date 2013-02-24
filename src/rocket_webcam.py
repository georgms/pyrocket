#!/usr/bin/python
import cv

from pygtk import require
require('2.0')
import gtk, gobject

# ==================================

class WebcamManager:

	def __init__(self):
		self.webcams = []

# ==================================

class VideoWindow(gtk.Frame):

	def __init__(self):

		gtk.Frame.__init__(self, "Video Source")


		master_vbox = gtk.VBox(False, 5)
		master_vbox.set_border_width( 5 )
		self.add( master_vbox )


		video_frame = gtk.Frame()
		self.video_image = gtk.Image()

		master_vbox.pack_start(video_frame, False, False)
		video_frame.add(self.video_image)

		# -----------------------------------

		self.video_enabled_button = gtk.ToggleButton("Enable Video")
		self.video_enabled_button.connect("clicked", self.cb_toggle_video)
		master_vbox.pack_start(self.video_enabled_button, False, False)

		# -----------------------------------

		self.inverted_video = gtk.CheckButton("Invert video")
		master_vbox.pack_start(self.inverted_video, False, False)

		# -----------------------------------


		self.capture = None

		self.cascade = cv.Load('haarcascade_frontalface_alt.xml')
		# create storage
		self.storage = cv.CreateMemStorage(0)
		
		self.threshold = 0
		
		self.faces = []

		master_vbox.show_all()

	# -----------------------------------

	def start_video(self):

		device = 0
		self.start_capture(device)
		self.initialize_video()

	# -----------------------------------

	def start_capture(self, device):

#		video_dimensions = [176, 144]
		video_dimensions = [320, 240]

                if not self.capture:

			self.capture = cv.CreateCameraCapture (device)
			
			cv.SetCaptureProperty(self.capture, cv.CV_CAP_PROP_FRAME_WIDTH, video_dimensions[0])
			cv.SetCaptureProperty(self.capture, cv.CV_CAP_PROP_FRAME_HEIGHT, video_dimensions[1])

	# -----------------------------------

	def stop_capture(self):
                if self.capture:
                	del(self.capture)

		self.capture = None

	# -----------------------------------

	def initialize_video(self):

		webcam_frame = cv.QueryFrame( self.capture )

		if not webcam_frame:
			print "Frame acquisition failed."
			return False

		self.webcam_pixbuf = gtk.gdk.pixbuf_new_from_data(
			webcam_frame.tostring(),
			gtk.gdk.COLORSPACE_RGB,
			False,
			8,
			webcam_frame.width,
			webcam_frame.height,
			webcam_frame.width * 3)
		self.video_image.set_from_pixbuf(self.webcam_pixbuf)


                self.display_frame = cv.CreateImage( (webcam_frame.width, webcam_frame.height), cv.IPL_DEPTH_8U, 3)

		return True

	# -----------------------------------

	def cb_toggle_video(self, widget):

		if widget.get_active():
			gobject.idle_add( self.run )

	# -------------------------------------------

	def run(self):

		if self.capture:
			webcam_frame = cv.QueryFrame( self.capture )
		else:
			print "Capture failed!"
			return

		if self.inverted_video.get_active():
			cv.ConvertImage(webcam_frame, webcam_frame, cv.CV_CVTIMG_FLIP)
		cv.ConvertImage(webcam_frame, self.display_frame, cv.CV_CVTIMG_SWAP_RB)

		# detect faces
		faces = cv.HaarDetectObjects(self.display_frame, self.cascade, self.storage, 1.2, 2, cv.CV_HAAR_DO_CANNY_PRUNING)
		
		# See if the face count changed, if so display a message
		if len(self.faces) != len(faces):
			if len(faces) == 0:
				print "No faces found"
			else:
				print "Found " + str(len(faces)) + " faces"
			
		if len(faces) == 1:
			face = faces[0]
			self.mark_face(face, self.display_frame)
			
		self.faces = faces
				
		incoming_pixbuf = gtk.gdk.pixbuf_new_from_data(
				self.display_frame.tostring(),
				gtk.gdk.COLORSPACE_RGB,
				False,
				8,
				self.display_frame.width,
				self.display_frame.height,
				self.display_frame.width * 3)
		incoming_pixbuf.copy_area(0, 0, self.display_frame.width, self.display_frame.height, self.webcam_pixbuf, 0, 0)

		self.video_image.queue_draw()


		return self.video_enabled_button.get_active()

	def mark_face(self, face, inputImage):
		""" Mark the given face in the given inputImage """
		
		position = face[0]
		left = position[0]
		top = position[1]
		right = left + position[2]
		bottom = top + position[3]
		
		# Mark the face
		color = (0, 255, 0)
		thickness = 1
		lineType = 8
		shift = 0
		cv.Rectangle(inputImage, (left, top), (right, bottom), color, thickness, lineType, shift)
		
		centerX = right - (right - left) / 2
		centerY = bottom - (bottom - top) / 2
		
		# Mark the center of the face
		radius = 5 
		cv.Circle(inputImage, (centerX, centerY), radius, color, thickness, lineType, shift)
		
		cv.Rectangle(inputImage,
			(left, top),
			(right, bottom),
			(0, 255, 0),
			3,
			8,
			0)
		
		diffX = centerX - inputImage.width / 2
		diffY = centerY - inputImage.height / 2
		
		# Draw a line from the center of the face to the center of the image as an indication how to move the launcher
		cv.Line(inputImage, (centerX, centerY), (inputImage.width / 2, inputImage.height / 2), color, thickness, lineType, shift)
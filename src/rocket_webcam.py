#!/usr/bin/python
import cv

from pygtk import require
require('2.0')
import gtk, gobject
import time

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
		self.previous_face = None

		# remember the last movement direction to be able to consistently move in 1 direction		
		self.last_movement = None

		master_vbox.show_all()
		
	def set_rocket_frontend(self, rocket_frontend):
		self.rocket_frontend = rocket_frontend

	# -----------------------------------

	def start_video(self):

		device = 1
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

		faces = self.detect_faces(self.display_frame, self.previous_face)
		
		# See if the face count changed, if so display a message
		if len(self.faces) != len(faces):
			if len(faces) == 0:
				print "No faces found"
			else:
				print "Found " + str(len(faces)) + " faces"
				
		self.previous_face = None
			
		if len(faces) == 1:
			
			# faces[0] is the first detected face, faces[0][0] is the position tuple of the first detected face
			face = faces[0][0]
			self.previous_face = face
			self.mark_face(face, self.display_frame)
			
			center = (self.display_frame.width / 2, self.display_frame.height / 2)
			target = (face[0] + face[2] / 2, face[1] + face[3])
			self.center_target(center, target)
		else:
			self.rocket_frontend.movement_wrapper(5)
			
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
	
	def detect_faces(self, input_image, previous_face = None):
		""" Detect a face in the given input_image, optionally provide a previous_face to speed up detection """
		
		offset_x = 0
		offset_y = 0
		
		scale_factor = 1.2
		min_neighbors = 2
		
		if previous_face != None:

			# extract a part of the original image that surrounds the previous face			
			area_of_interest = self.find_area_of_interest(previous_face, (input_image.width, input_image.height))
			input_image = cv.GetSubRect(input_image, area_of_interest)
			
			# the coordinates of the detected faces need to offset as the detection is based on a sub-section of the original image			
			offset_x = area_of_interest[0]
			offset_y = area_of_interest[1]

		cv.ShowImage('focus', input_image)
		
		begin_face_detection = int(round(time.time() * 1000))
		faces = cv.HaarDetectObjects(input_image, self.cascade, self.storage, scale_factor, min_neighbors, cv.CV_HAAR_DO_CANNY_PRUNING)
		end_face_detection = int(round(time.time() * 1000))
		
		print 'face detection took [ms]', end_face_detection - begin_face_detection

		# Offset the detected faces if necessary
		if offset_x > 0 or offset_y > 0:
					
			offset_faces = []
			
			for face in faces:
				position = face[0]
				neighbors = face[1]
				offset_position = (position[0] + offset_x, position[1] + offset_y, position[2], position[3])
				
				offset_face = (offset_position, neighbors)
				offset_faces.append(offset_face)
			
			faces = offset_faces
		
		return faces

	def find_area_of_interest(self, previous_face, max_dimensions):
		""" Find the area of interest by calculating a rectangle around a previously detected face """
		
		previous_face_left = previous_face[0]
		previous_face_top = previous_face[1]
		previous_face_width = previous_face[2]
		previous_face_height = previous_face[3]
		
		previous_face_center_x = previous_face_left + previous_face_width / 2
		previous_face_center_y = previous_face_top + previous_face_height / 2
		
		# focus on the are where the last face was detected, extend the area by extend_factor in all directions (0 = no extension)
		extend_factor = 1.0

		# how far in pixels to extend to the left/right and top/bottom		
		extend_x = previous_face_width * extend_factor
		extend_y = previous_face_height * extend_factor
		
		# calculate the area of interest's coordinates
		area_of_interest_left = int(round(max(0, previous_face_center_x - extend_x)))
		area_of_interest_right = int(round(min(max_dimensions[0], previous_face_center_x + extend_x)))
		area_of_interest_top = int(round(max(0, previous_face_center_y - extend_y)))
		area_of_interest_bottom = int(round(min(max_dimensions[1], previous_face_center_y + extend_y)))
		
		area_of_interest = (area_of_interest_left, area_of_interest_top, area_of_interest_right - area_of_interest_left, area_of_interest_bottom - area_of_interest_top)
		return area_of_interest
		
		
	def mark_face(self, face, inputImage):
		""" Mark the given face in the given inputImage """
		
		left = face[0]
		top = face[1]
		right = left + face[2]
		bottom = top + face[3]
		
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
		
		(diff_x, diff_y) = self.get_diff_vector((centerX, centerY), (self.display_frame.width / 2, self.display_frame.height / 2))
		
		# Draw a line from the center of the face to the center of the image as an indication how to move the launcher
		cv.Line(inputImage, (centerX, centerY), (inputImage.width / 2, inputImage.height / 2), color, thickness, lineType, shift)
		
	def get_diff_vector(self, point1, point2):
		""" Get the vector between two points """
		
		diff_x = point1[0] - point2[0]
		diff_y = point1[1] - point2[1]
		return (diff_x, diff_y)
	
	def center_target(self, center, target):
		""" Rotate / Tilt the rocket launcher so that the target gets in the center of the view """
		 
		diff = self.get_diff_vector(target, center)
		
		DOWN = 0
		UP = 1
		LEFT = 2
		RIGHT = 3
		
		STOP = 5
		
		print 'diff', diff, self.last_movement
		
		# move only when the diff is bigger than this to avoid jumping around the center
		movement_threshold = 25
		
		if self.rocket_frontend:
			
			if (self.last_movement == None or self.last_movement == LEFT) and diff[0] < -movement_threshold:
				self.rocket_frontend.movement_wrapper(LEFT)
				self.last_movement = LEFT
				print "turn left"
			elif (self.last_movement == None or self.last_movement == RIGHT) and diff[0] > movement_threshold:
				self.rocket_frontend.movement_wrapper(RIGHT)
				self.last_movement = RIGHT
				print "turn right"
			elif (self.last_movement == None or self.last_movement == DOWN) and diff[1] > movement_threshold:
				self.rocket_frontend.movement_wrapper(DOWN)
				self.last_movement = DOWN
				print "turn down"
			elif (self.last_movement == None or self.last_movement == UP) and diff[1] < -movement_threshold:
				self.rocket_frontend.movement_wrapper(UP)
				self.last_movement = UP
				print "turn up"
			else:
				print "Stop all engines"
				self.rocket_frontend.movement_wrapper(STOP)
				self.last_movement = None
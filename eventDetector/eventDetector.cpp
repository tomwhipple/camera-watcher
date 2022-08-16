/*
 * eventDetector.cpp
 *
 *  Created on: Jul 19, 2022
 *      Author: tw
 */

#include <time.h>

#include <iostream>
#include <string>
#include <sstream>
#include <vector>
#include <tuple>
#include <list>
#include <algorithm>

// are these needed??
#include <functional>
#include <unordered_map>
#include <utility>

#include <opencv2/videoio.hpp>
#include <opencv2/imgproc.hpp>
#include <opencv2/core.hpp>
#include <opencv2/highgui.hpp>

#include <opencv2/gapi.hpp>
#include <opencv2/gapi/core.hpp>
#include <opencv2/gapi/imgproc.hpp>
#include <opencv2/gapi/cpu/gcpukernel.hpp>

using namespace std;
using namespace cv;

#define NUM_BG_FRAMES 10
#define MAX_BG_SECONDS 45
#define BG_THRESHOLD 125
#define RECT_GROW_FACTOR 3

#define GREEN Scalar(0, 255,0)
#define WHITE Scalar(255,255,255)

const int scale = 2;

bool filterRect(Rect* r) {
	return (
//		r->area() > 100/scale &&
		r->y > 40/scale
	);
}

inline void growRect(Rect* r) {
	const int gf = RECT_GROW_FACTOR;
	r->x -= gf;
	r->y -= gf;
	r->height += 2*gf;
	r->width += 2*gf;
}

inline bool inInterval(int begin, int test, int end) {
	return (begin <= test && test <= end);
}
inline bool isRectOverlap(Rect r1, Rect r2) {
//	return (r1.x <= r2.x <= r1.x + r1.width)
//		&& (r1.y <= r2.y <= r1.y + r1.height
//			|| r1.y <= r2.y + r2.height <= r1.y + r2.height
//			|| r2.y <= r1.y <= r2.y + r2.height
//			|| r2.y <= r1.y + r1.height <= r2.y + r2.height);
	return (inInterval(r1.x, r2.x, r1.x +r1.width)
			&& (inInterval(r1.y, r2.y, r1.y + r1.height)
				|| inInterval(r1.y, r2.y + r2.height, r1.y + r2.height)
				|| inInterval(r2.y, r1.y, r2.y + r2.height)
				|| inInterval(r2.y, r1.y + r1.height, r2.y + r2.height)
			   )
	);
}

inline Rect mergeOverlapping(Rect r1, Rect r2) {
	Point p = Point(min(r1.x, r2.x), min(r1.y,r2.y));
	Size s = Size(max(r1.x+r1.width, r2.x+r2.width) - p.x, max(r1.y+r1.height, r2.y+r2.height) - p.y);
	return Rect(p, s);
}

inline bool compareRectByX(Rect r1, Rect r2) {
	return (r1.x < r2.x);
}

void mergeBoxes(vector<Rect> &boxes) {
	if (boxes.size() <= 1) {
		return;
	}

	sort(boxes.begin(), boxes.end(), compareRectByX);

	for (auto it1 = boxes.begin(); it1 != boxes.end(); ++it1) {
		auto it2 = it1+1;
		while (it2 != boxes.end()) {
//			cout << "rect " << *it1 << " & " << *it2;
			if (isRectOverlap(*it1, *it2)) {
//				cout << " overlap";
				*it1 = mergeOverlapping(*it1, *it2);
				it2 = boxes.erase(it2); // @suppress("Invalid arguments")
			}
			else {
//				cout << " distinct";
				++it2;
			}
//			cout << endl;
		}
	}
}

// example from https://github.com/opencv/opencv/issues/21524

namespace custom {

  G_API_OP(ToBoundingRects, <cv::GArray<cv::Rect>(cv::GArray<cv::GArray<cv::Point>>)>, "custom.fd_ToBoundingRects") {
    static cv::GArrayDesc outMeta(const cv::GArrayDesc&) {
      // This function is required for G-API engine to figure out
      // what the output format is, given the input parameters.
      // Since the output is an array (with a specific type),
      // there's nothing to describe.
      return cv::empty_array_desc();
    }
  };


  GAPI_OCV_KERNEL(OCVToBoundingRects, ToBoundingRects) {
    static void run(const std::vector<std::vector<cv::Point>> &in_contours,
                    std::vector<cv::Rect> &out_boundingRects) {
      out_boundingRects.clear();
      cv::Rect br;
      for (auto c : in_contours) {
        br = cv::boundingRect(c);
        if ( filterRect(&br) ) {
        	growRect(&br);
        	out_boundingRects.push_back(br);
        }
      }
      mergeBoxes(out_boundingRects);
    }
  };

} // namespace custom

GComputation createDetectionGraph() {
	// set up main computation
	Mat kernel = Mat::ones(Size(3,3), CV_8U);

	GMat in;
	GMat bg;
	GMat diff = gapi::absDiff(in, bg);
	GMat gray_diff = gapi::BGR2Gray(diff);
	GMat blurred = gapi::morphologyEx(gray_diff, MORPH_CLOSE, kernel);
	GMat thresh = gapi::threshold(blurred, BG_THRESHOLD, 255, THRESH_BINARY);
	GArray<GArray<cv::Point>> contours = gapi::findContours(thresh,RETR_EXTERNAL, CHAIN_APPROX_NONE);
	GArray<cv::Rect> boundingRects = custom::ToBoundingRects::on(contours);

	return GComputation (cv::GIn(in, bg), cv::GOut(thresh, contours, boundingRects));
}


void showDebugImage(Mat image, vector<Rect> boxes, int scale = 1) {
	auto frameHeight = image.size().height;

	for (auto b : boxes) {
		auto sc_b = Rect(b.x * scale, b.y * scale, b.width * scale, b.height * scale);
		rectangle(image, sc_b, GREEN, 1);
	}
	stringstream msg;
	msg << "Found " << boxes.size() << " objects";
	putText(image, msg.str(), Point(5,frameHeight - 5), FONT_HERSHEY_SIMPLEX, 0.75 , WHITE);

	imshow("Video detections", image);
}

void getMeanBackground(list<Mat>* buffer, Mat* mean_bg) {
	Mat bg_accum = Mat::zeros(buffer->front().size(), CV_32FC3);
	for (auto f : *buffer) {
		bg_accum += f;
	}
	bg_accum /= buffer->size();
	bg_accum.convertTo(*mean_bg, CV_8UC3);
}

void testRelational() {
	cout << ((1 <= 2 <= 3)?"true":"false") << endl;
	cout << ((1 <= -2 <= 3)?"true":"false") << endl;
	cout << ((1 <= 2 <= -3)?"true":"false") << endl;

	cout << (inInterval(1, 2, 3)?"true":"false") << endl;
	cout << (inInterval(1, -2, 3)?"true":"false") << endl;
	cout << (inInterval(1, 2, -4)?"true":"false") << endl;
}

int main(int argc, char *argv[]) {

	time_t now;
	time(&now);
	time_t bg_captured_at = 0;

	VideoCapture cap;
	if (argc > 1) {
		cap.open(argv[1]);
		cout << "opened " << argv[1] << endl;
	}
	else cap.open(0); //default OS webcam. Probably won't work on MacOSX

	Mat frame;
	cap.read(frame); // just for size info

	auto work_frame = Mat();
	auto frame_buffer = list<Mat>();
	auto background = Mat();

	vector<vector<cv::Point>> contours_out;
	Mat display_out;
	vector<cv::Rect> boxes_out;

	cv::gapi::GKernelPackage kernels = cv::gapi::kernels<custom::OCVToBoundingRects>();

	auto motionContours = createDetectionGraph();
	cout << "starting at " << now << endl;
	while (cap.isOpened() && waitKey(30) < 0 && cap.read(frame))  {
		time(&now);

		pyrDown(frame, work_frame, Size(frame.cols/scale, frame.rows/scale));
		if (work_frame.size().area() > 0) frame_buffer.push_back(work_frame);

		if (difftime(now, bg_captured_at) > MAX_BG_SECONDS && frame_buffer.size() >= NUM_BG_FRAMES) {
			time(&bg_captured_at);
			getMeanBackground(&frame_buffer, &background);
			cout << "captured background at " << asctime(localtime(&now)) << endl;
		}

		if (frame_buffer.size() >= NUM_BG_FRAMES) {
			motionContours.apply(cv::gin(work_frame, background), cv::gout(display_out, contours_out, boxes_out),cv::compile_args(kernels));
			showDebugImage(frame, boxes_out, scale);
//			imshow("background", background);
			imshow("threshold", display_out);
			frame_buffer.pop_front();
		}

	}
	cout << "done!\n";
}

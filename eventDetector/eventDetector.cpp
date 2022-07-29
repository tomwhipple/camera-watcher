/*
 * eventDetector.cpp
 *
 *  Created on: Jul 19, 2022
 *      Author: tw
 */

#include <iostream>
#include <string>
#include <vector>
#include <tuple>

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

/*
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
    static void run(const std::vector<std::vector<cv::Point2i>> &in_contours,
                    std::vector<cv::Rect> &out_boundingRects) {
      out_boundingRects.clear();
      cv::Rect br;
      for (auto c : in_contours) {
        br = cv::gapi::boundingRect(c);
        out_boundingRects.push_back(br);
      }
    }
  };

} // namespace custom
*/

GComputation createDetectionGraph() {
	// set up main computation
	Mat kernel = Mat::ones(Size(3,3), CV_8U);

	GMat in;
	GMat bg;
	GMat diff = gapi::absDiff(in, bg);
	GMat gray_diff = gapi::BGR2Gray(diff);
	GMat blurred = gapi::morphologyEx(gray_diff, MORPH_CLOSE, kernel);
	GMat thresh = gapi::threshold(blurred, 128, 255, THRESH_BINARY);
	GArray<GArray<cv::Point>> contours = gapi::findContours(thresh, RETR_LIST, CHAIN_APPROX_NONE);

	return GComputation (cv::GIn(in, bg), cv::GOut(thresh, contours));
}

int main(int argc, char *argv[]) {

	VideoCapture cap;
	if (argc > 1) {
		cap.open(argv[1]);
		cout << "opened " << argv[1] << endl;
	}
	else cap.open(0); //default OS webcam. Probably won't work on MacOSX

	Mat frame;
	cap.read(frame); // just for size info

	Mat work_frame;

	Mat bg_accum;
	Mat mean_bg;
	bool has_initial_bg = false;
	int has_bg_frames = 0;

	vector<vector<cv::Point>> contours_out;
	Mat display_out;

	auto motionContours = createDetectionGraph();

	while (cap.isOpened() && waitKey(30) < 0)  {
		cap.read(frame);
		pyrDown(frame, work_frame, Size(frame.cols/2, frame.rows/2));

		if (has_bg_frames < NUM_BG_FRAMES) {
			if (has_bg_frames == 0) {
				bg_accum = Mat::zeros(work_frame.size(), CV_32FC3);
			}

			bg_accum += work_frame;
			has_bg_frames += 1;
		}
		if (has_bg_frames == NUM_BG_FRAMES) {
			mean_bg = bg_accum / has_bg_frames;
			mean_bg.convertTo(mean_bg, CV_8UC3);
			has_initial_bg = true;
		}
		if (has_initial_bg) {
			motionContours.apply(cv::gin(work_frame, mean_bg), cv::gout(display_out, contours_out));
			imshow("output", display_out);
		}

	}
}

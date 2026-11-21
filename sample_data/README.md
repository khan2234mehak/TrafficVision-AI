# Sample data

TrafficVision AI does **not** ship a traffic video (that would risk copyright and bloat the ZIP).
You can still try everything in three ways:

1. **Demo mode (no video needed).** The dashboard, analytics, map, violations and reports are pre-filled
   with simulated data. Every simulated number or record is labelled **DEMO**. Hide it any time in
   *Settings -> Appearance and data*.
2. **Upload any traffic video** on the *Video Analysis* page (MP4/AVI/MOV). This produces real AI results.
3. **Register a recorded sample as a camera.** Copy an `.mp4` into this folder, then in
   *Camera Management* add a camera with source "Recorded sample video". It plays once through the real
   pipeline in *Live Monitoring* (it is a recording, not a live CCTV feed, and the UI says so).

## Where to get free traffic footage

Use clips whose licence allows reuse, and check the licence yourself before redistributing:

* Pexels (https://www.pexels.com/search/videos/traffic/) and Pixabay (https://pixabay.com/videos/search/traffic/)
  - free-to-use licences (no attribution required, but read the current terms).
* Your own phone footage from a bridge / balcony looking down at a road works very well.

Tips for good results: a fixed camera, a slightly elevated view, daylight, 720p-1080p, 20-30 fps.
Large video files in this folder are ignored by git (see `.gitignore`).

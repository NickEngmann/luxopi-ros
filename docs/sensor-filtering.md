# Distance filtering and safety

The VL53L4CD driver reports centimetres, while the dashboard/API uses metres.
The publisher converts at that boundary. The driver's range envelope follows
[ST's VL53L4CD specification](https://www.st.com/resource/en/datasheet/vl53l4cd.pdf):
up to 1200 mm. Zero is handled conservatively as immediate danger; negative,
nonfinite, or greater-than-120 cm readings invalidate coverage.

The previous median filter could replace a sudden 2 cm obstacle with older
100 cm clear readings. The shared pure filter now never reports more clearance
than the latest valid observation. It still filters increasing clearances
conservatively. Invalid samples reset filter history, publish an invalid reading
to the classifier, and do not refresh the I2C driver's last-success timestamp.
Missing data and explicit invalid data cannot clear a latched contact.

Offline tests cover sudden approach, delayed clearance recovery, zero/sub-centimetre
observations, invalid-data reset, and the actual driver's read method without
opening I2C hardware. These verify software behavior; they do not establish
physical sensor accuracy, cover-window performance, mount orientation, or stopping
distances. Both range and contact inputs remain subject to freshness checks.

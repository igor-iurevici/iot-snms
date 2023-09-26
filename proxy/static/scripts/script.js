function updateDataValues() {
  // Make an AJAX request to fetch the latest RSSI value
  fetch('/get_latest_data')
    .then(response => response.json())
    .then(data => {
      var noiseValue = data.noise_value;
      var alarmFlag = data.alarm_flag;
      var rssiValue = data.rssi_value;
      var noiseClass = 'high';
      var alarmClass = 'high';
      var rssiClass = 'high';
      
      // RSSI value range color
      if (rssiValue >= -40) {
        rssiClass = 'low';
      } else if (rssiValue < -40 && rssiValue >= -105) {
        rssiClass = 'medium';
      } else {
        rssiClass = 'high';
      }

      // Noise value range color
      if (noiseValue < 50) {
        noiseClass = 'low';
      } else if (noiseValue >= 50 && noiseValue <=65)
      { 
        noiseClass = 'medium';
      } else {
        noiseClass = 'high';
      }

      // Alarm color
      if (alarmFlag == 0) {
        alarmFlag = 'OFF'
        alarmClass = 'low';
      } else {
        alarmFlag = 'ON'
        alarmClass = 'high';
      }
      
      // Update the HTML element with the latest RSSI value and color class
      var rssiValueElement = document.getElementById('rssi_value');
      rssiValueElement.textContent = rssiValue;
      rssiValueElement.className = rssiClass;

      var noiseValueElement = document.getElementById('noise_value');
      noiseValueElement.textContent = noiseValue;
      noiseValueElement.className = noiseClass;

      var alarmFlagElement = document.getElementById('alarm_flag');
      alarmFlagElement.textContent = alarmFlag;
      alarmFlagElement.className = alarmClass;
      
      setTimeout(updateDataValues, 1000);
    });
}

updateDataValues();

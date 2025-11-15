/// Weather Data Model
///
/// Represents weather information for garden planning and care recommendations.
class WeatherData {
  /// Location
  final String location;
  final double? latitude;
  final double? longitude;

  /// Current weather
  final double temperatureCelsius;
  final double? feelsLikeCelsius;
  final int humidity;
  final String condition;
  final String? description;
  final String? iconCode;

  /// Precipitation
  final double? precipitationMm;
  final int? precipitationProbability;

  /// Wind
  final double? windSpeedKmh;
  final String? windDirection;

  /// UV and sun
  final double? uvIndex;
  final DateTime? sunrise;
  final DateTime? sunset;

  /// Timestamp
  final DateTime timestamp;

  const WeatherData({
    required this.location,
    this.latitude,
    this.longitude,
    required this.temperatureCelsius,
    this.feelsLikeCelsius,
    required this.humidity,
    required this.condition,
    this.description,
    this.iconCode,
    this.precipitationMm,
    this.precipitationProbability,
    this.windSpeedKmh,
    this.windDirection,
    this.uvIndex,
    this.sunrise,
    this.sunset,
    required this.timestamp,
  });

  /// Create from OpenWeatherMap API response
  factory WeatherData.fromOpenWeatherMap(Map<String, dynamic> json) {
    final main = json['main'] as Map<String, dynamic>;
    final weather = (json['weather'] as List<dynamic>)[0] as Map<String, dynamic>;
    final wind = json['wind'] as Map<String, dynamic>?;
    final sys = json['sys'] as Map<String, dynamic>?;
    final coord = json['coord'] as Map<String, dynamic>?;

    return WeatherData(
      location: json['name'] as String,
      latitude: coord?['lat'] as double?,
      longitude: coord?['lon'] as double?,
      temperatureCelsius: (main['temp'] as num).toDouble() - 273.15, // Convert from Kelvin
      feelsLikeCelsius: main['feels_like'] != null
          ? (main['feels_like'] as num).toDouble() - 273.15
          : null,
      humidity: main['humidity'] as int,
      condition: weather['main'] as String,
      description: weather['description'] as String?,
      iconCode: weather['icon'] as String?,
      precipitationMm: json['rain'] != null
          ? ((json['rain'] as Map<String, dynamic>)['1h'] as num?)?.toDouble()
          : null,
      precipitationProbability: null, // Not in current weather
      windSpeedKmh: wind != null ? (wind['speed'] as num).toDouble() * 3.6 : null, // m/s to km/h
      windDirection: wind?['deg'] != null
          ? _degreesToCardinal(wind!['deg'] as int)
          : null,
      uvIndex: null, // Requires separate UV Index API call
      sunrise: sys?['sunrise'] != null
          ? DateTime.fromMillisecondsSinceEpoch((sys!['sunrise'] as int) * 1000)
          : null,
      sunset: sys?['sunset'] != null
          ? DateTime.fromMillisecondsSinceEpoch((sys!['sunset'] as int) * 1000)
          : null,
      timestamp: DateTime.now(),
    );
  }

  /// Convert wind degrees to cardinal direction
  static String _degreesToCardinal(int degrees) {
    const directions = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW'];
    return directions[((degrees + 22.5) / 45).floor() % 8];
  }

  /// Temperature in Fahrenheit
  double get temperatureFahrenheit => (temperatureCelsius * 9 / 5) + 32;

  /// Is it currently raining?
  bool get isRaining => condition.toLowerCase().contains('rain');

  /// Is it good weather for gardening?
  bool get isGoodForGardening {
    // Not too hot, not raining heavily, not too windy
    final tempOk = temperatureCelsius >= 10 && temperatureCelsius <= 30;
    final notHeavyRain = (precipitationMm ?? 0) < 5;
    final notTooWindy = (windSpeedKmh ?? 0) < 30;
    return tempOk && notHeavyRain && notTooWindy;
  }

  /// Get watering recommendation
  String get wateringRecommendation {
    if (isRaining && (precipitationMm ?? 0) > 2) {
      return 'Skip watering - adequate rainfall expected';
    } else if (temperatureCelsius > 30 || humidity < 30) {
      return 'Water plants thoroughly - hot and dry conditions';
    } else if (temperatureCelsius > 25) {
      return 'Water if soil is dry - warm weather';
    } else {
      return 'Check soil moisture before watering';
    }
  }
}

/// Weather Forecast Data
class WeatherForecast {
  final DateTime date;
  final double temperatureMinCelsius;
  final double temperatureMaxCelsius;
  final String condition;
  final String? description;
  final String? iconCode;
  final int? precipitationProbability;
  final double? precipitationMm;

  const WeatherForecast({
    required this.date,
    required this.temperatureMinCelsius,
    required this.temperatureMaxCelsius,
    required this.condition,
    this.description,
    this.iconCode,
    this.precipitationProbability,
    this.precipitationMm,
  });

  /// Create from OpenWeatherMap forecast API response
  factory WeatherForecast.fromOpenWeatherMap(Map<String, dynamic> json) {
    final main = json['main'] as Map<String, dynamic>;
    final weather = (json['weather'] as List<dynamic>)[0] as Map<String, dynamic>;

    return WeatherForecast(
      date: DateTime.fromMillisecondsSinceEpoch((json['dt'] as int) * 1000),
      temperatureMinCelsius: (main['temp_min'] as num).toDouble() - 273.15,
      temperatureMaxCelsius: (main['temp_max'] as num).toDouble() - 273.15,
      condition: weather['main'] as String,
      description: weather['description'] as String?,
      iconCode: weather['icon'] as String?,
      precipitationProbability: json['pop'] != null
          ? ((json['pop'] as num) * 100).toInt()
          : null,
      precipitationMm: json['rain'] != null
          ? ((json['rain'] as Map<String, dynamic>)['3h'] as num?)?.toDouble()
          : null,
    );
  }

  /// Temperature range in Fahrenheit
  String get temperatureRangeFahrenheit {
    final min = (temperatureMinCelsius * 9 / 5) + 32;
    final max = (temperatureMaxCelsius * 9 / 5) + 32;
    return '${min.round()}°F - ${max.round()}°F';
  }
}

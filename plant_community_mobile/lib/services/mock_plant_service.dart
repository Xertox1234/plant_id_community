import 'dart:math';
import '../models/plant.dart';

/// Mock plant identification service for development
///
/// Simulates API calls with mock plant database
class MockPlantService {
  /// Mock plant database (from design_reference/src/components/PlantCamera.tsx)
  static final List<Plant> _mockPlants = [
    Plant(
      id: '1',
      name: 'Echeveria',
      scientificName: 'Echeveria elegans',
      description:
          'A popular succulent with rosette-shaped leaves, often called "Mexican Snowball". '
          'Known for its stunning blue-green color and low maintenance requirements.',
      care: [
        'Water sparingly, allowing soil to dry completely',
        'Requires bright, direct sunlight (4-6 hours)',
        'Well-draining soil is essential',
        'Thrives in temperatures 65-80°F',
      ],
      timestamp: DateTime.now(),
    ),
    Plant(
      id: '2',
      name: 'Boston Fern',
      scientificName: 'Nephrolepis exaltata',
      description:
          'A lush, feathery fern with arching fronds. This classic houseplant is excellent '
          'for adding greenery and humidity to indoor spaces.',
      care: [
        'Keep soil consistently moist but not soggy',
        'Prefers indirect, filtered light',
        'High humidity is essential',
        'Mist regularly to maintain moisture',
      ],
      timestamp: DateTime.now(),
    ),
    Plant(
      id: '3',
      name: 'Monstera Deliciosa',
      scientificName: 'Monstera deliciosa',
      description:
          'Also known as the Swiss Cheese Plant, famous for its large, glossy leaves with '
          'natural holes. A trendy and easy-to-grow tropical plant.',
      care: [
        'Water when top inch of soil is dry',
        'Bright, indirect light is ideal',
        'Wipe leaves regularly to remove dust',
        'Provide a moss pole for support',
      ],
      timestamp: DateTime.now(),
    ),
    Plant(
      id: '4',
      name: 'English Lavender',
      scientificName: 'Lavandula angustifolia',
      description:
          'An aromatic herb with beautiful purple flower spikes. Valued for its fragrance, '
          'medicinal properties, and ability to attract pollinators.',
      care: [
        'Water moderately, drought-tolerant once established',
        'Full sun (6-8 hours) required',
        'Well-drained, slightly alkaline soil',
        'Prune after flowering to maintain shape',
      ],
      timestamp: DateTime.now(),
    ),
  ];

  /// Mock sample images (from Unsplash)
  static final List<String> sampleImages = [
    'https://images.unsplash.com/photo-1717130082324-00781001faba?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&ixid=M3w3Nzg4Nzd8MHwxfHNlYXJjaHwxfHxzdWNjdWxlbnQlMjBwbGFudCUyMGNsb3NlfGVufDF8fHx8MTc2MTA1OTEwOHww&ixlib=rb-4.1.0&q=80&w=1080',
    'https://images.unsplash.com/photo-1680593384685-1d8c68f37872?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&ixid=M3w3Nzg4Nzd8MHwxfHNlYXJjaHwxfHxmZXJuJTIwbGVhdmVzJTIwbmF0dXJlfGVufDF8fHx8MTc2MTA1OTEwOHww&ixlib=rb-4.1.0&q=80&w=1080',
    'https://images.unsplash.com/photo-1648528203163-8604bf696e7c?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&ixid=M3w3Nzg4Nzd8MHwxfHNlYXJjaHwxfHxtb25zdGVyYSUyMHBsYW50JTIwaW5kb29yfGVufDF8fHx8MTc2MTAxNjkzOXww&ixlib=rb-4.1.0&q=80&w=1080',
    'https://images.unsplash.com/photo-1631791222734-2f1cb65e2fa9?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&ixid=M3w3Nzg4Nzd8MHwxfHNlYXJjaHwxfHxsYXZlbmRlciUyMGZsb3dlcnMlMjBmaWVsZHxlbnwxfHx8fDE3NjEwMjEzMTh8MA&ixlib=rb-4.1.0&q=80&w=1080',
  ];

  /// Identify a plant from an image (mock implementation)
  ///
  /// Simulates a 2-second API call and returns a random plant
  static Future<Plant> identifyPlant(String imagePath) async {
    // Simulate API delay
    await Future.delayed(const Duration(seconds: 2));

    // Pick a random plant from mock database
    final random = Random();
    final randomIndex = random.nextInt(_mockPlants.length);
    final mockPlant = _mockPlants[randomIndex];

    // Return plant with the user's image
    return mockPlant.copyWith(
      id: DateTime.now().millisecondsSinceEpoch.toString(),
      imageUrl: imagePath,
      timestamp: DateTime.now(),
    );
  }

  /// Get all mock plants
  static List<Plant> getAllPlants() {
    return List.unmodifiable(_mockPlants);
  }

  /// Get a specific plant by ID
  static Plant? getPlantById(String id) {
    try {
      return _mockPlants.firstWhere((plant) => plant.id == id);
    } catch (e) {
      return null;
    }
  }
}

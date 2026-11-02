import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:mind_ai/const/api_constants.dart';

class LearningPathRepo {
  // Fetch existing or generate new learning path for a PDF
  Future<Map<String, dynamic>> getLearningPath({
    required String token,
    required int pdfId,
  }) async {
    final url = Uri.parse('${ApiConstants.baseUrl}/pdf/$pdfId/learning-path');

    final response = await http.get(
      url,
      headers: {
        'Authorization': 'Bearer $token',
        'Content-Type': 'application/json',
      },
    );

    if (response.statusCode == 200) {
      return jsonDecode(response.body) as Map<String, dynamic>;
    }

    throw Exception(
      'Failed to load learning path: ${response.statusCode} ${response.body}',
    );
  }

  // Request AI Teacher explanation for a specific topic in a PDF
  Future<Map<String, dynamic>> explainTopic({
    required String token,
    required int pdfId,
    required String topic,
    String depth = 'beginner',
  }) async {
    final url = Uri.parse('${ApiConstants.baseUrl}/pdf/$pdfId/explain');

    final response = await http.post(
      url,
      headers: {
        'Authorization': 'Bearer $token',
        'Content-Type': 'application/json',
      },
      body: jsonEncode({
        'topic': topic,
        'depth': depth,
      }),
    );

    if (response.statusCode == 200) {
      return jsonDecode(response.body) as Map<String, dynamic>;
    }

    throw Exception(
      'Failed to explain topic: ${response.statusCode} ${response.body}',
    );
  }
}

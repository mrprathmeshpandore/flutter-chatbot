
import 'dart:convert';

import 'package:http/http.dart' as http;
import 'package:mind_ai/const/api_constants.dart';

class QuizRepo {
  // Generate a new quiz
  Future<Map<String, dynamic>> generateQuiz({
    required String token,
    required int pdfId,
    int numQuestions = 5,
    String difficulty = 'medium',
  }) async {
    final url = Uri.parse(
      '${ApiConstants.baseUrl}/quiz/generate',
    );

    final response = await http.post(
      url,
      headers: {
        'Authorization': 'Bearer $token',
        'Content-Type': 'application/json',
      },
      body: jsonEncode({
        'pdf_id': pdfId,
        'num_questions': numQuestions,
        'difficulty': difficulty,
      }),
    );

    if (response.statusCode == 200 ||
        response.statusCode == 201) {
      return Map<String, dynamic>.from(
        jsonDecode(response.body) as Map,
      );
    }

    throw Exception(
      'Failed to generate quiz: '
      '${response.statusCode} ${response.body}',
    );
  }

  // Submit quiz answers
  Future<Map<String, dynamic>> submitQuiz({
    required String token,
    required int quizId,
    required List<Map<String, dynamic>> answers,
  }) async {
    final url = Uri.parse(
      '${ApiConstants.baseUrl}/quiz/submit',
    );

    final response = await http.post(
      url,
      headers: {
        'Authorization': 'Bearer $token',
        'Content-Type': 'application/json',
      },
      body: jsonEncode({
        'quiz_id': quizId,
        'answers': answers,
      }),
    );

    if (response.statusCode == 200) {
      return Map<String, dynamic>.from(
        jsonDecode(response.body) as Map,
      );
    }

    throw Exception(
      'Failed to submit quiz: '
      '${response.statusCode} ${response.body}',
    );
  }

  // Get quiz results
  Future<Map<String, dynamic>> getQuizResults({
    required String token,
    required int quizId,
  }) async {
    final url = Uri.parse(
      '${ApiConstants.baseUrl}/quiz/$quizId/results',
    );

    final response = await http.get(
      url,
      headers: {
        'Authorization': 'Bearer $token',
        'Content-Type': 'application/json',
      },
    );

    if (response.statusCode == 200) {
      return Map<String, dynamic>.from(
        jsonDecode(response.body) as Map,
      );
    }

    throw Exception(
      'Failed to load quiz results: '
      '${response.statusCode} ${response.body}',
    );
  }
}

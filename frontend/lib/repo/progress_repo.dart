import 'package:http/http.dart' as http;
import 'package:mind_ai/const/api_constants.dart';
import 'package:mind_ai/model/progress_summary.dart';
import 'dart:convert';

class ProgressRepo {
  Future<ProgressSummary> getProgressSummary({required String token}) async {
    final url = Uri.parse('${ApiConstants.baseUrl}/progress/summary');
    final response = await http.get(
      url,
      headers: {
        "Authorization": "Bearer $token",
        "Content-Type": "application/json",
      },
    );
    if (response.statusCode == 200) {
      return ProgressSummary.fromJson(
        jsonDecode(response.body) as Map<String, dynamic>,
      );
    } else {
      throw Exception(
        "Failed to load progress: ${response.statusCode} ${response.body},",
      );
    }
  }
}

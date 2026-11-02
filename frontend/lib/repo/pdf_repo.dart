import 'dart:convert';

import 'package:http/http.dart' as http;
import 'package:mind_ai/const/api_constants.dart';
import 'package:mind_ai/model/pdf_model.dart';

class PdfRepo {
  Future<List<PdfModel>> getPdfs({required String token}) async {
    final url = Uri.parse('${ApiConstants.baseUrl}/pdf/');

    final response = await http.get(
      url,
      headers: {
        'Authorization': 'Bearer $token',
        'Content-Type': 'application/json',
      },
    );

    if (response.statusCode == 200) {
      final List<dynamic> data = jsonDecode(response.body);

      return data
          .map((item) => PdfModel.fromJson(item as Map<String, dynamic>))
          .toList();
    }

    throw Exception(
      'Failed to load PDFs: ${response.statusCode} ${response.body}',
    );
  }

  Future<void> deletePdf({required String token, required int pdfId}) async {
    final url = Uri.parse('${ApiConstants.baseUrl}/pdf/$pdfId');

    final response = await http.delete(
      url,
      headers: {
        'Authorization': 'Bearer $token',
        'Content-Type': 'application/json',
      },
    );

    if (response.statusCode != 200) {
      throw Exception(
        'Failed to delete PDF: ${response.statusCode} ${response.body}',
      );
    }
  }
}

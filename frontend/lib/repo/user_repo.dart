import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';
import 'package:mind_ai/const/api_constants.dart';
import 'package:mind_ai/model/user_model.dart';

class UserRepo {
  static const String _cachedUserKey = 'mindvault_cached_user_profile';

  Future<UserModel> getProfile({required String token}) async {
    final url = Uri.parse('${ApiConstants.baseUrl}/auth/me');

    final response = await http.get(
      url,
      headers: {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer $token',
      },
    );

    if (response.statusCode == 200) {
      final data = jsonDecode(response.body) as Map<String, dynamic>;
      final user = UserModel.fromJson(data);
      await _cacheUser(response.body);
      return user;
    } else {
      final errorData = jsonDecode(response.body);
      throw Exception(
        errorData is Map && errorData['detail'] != null
            ? errorData['detail'].toString()
            : 'Failed to fetch user profile',
      );
    }
  }

  Future<UserModel?> getCachedProfile() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final cachedJson = prefs.getString(_cachedUserKey);
      if (cachedJson != null && cachedJson.isNotEmpty) {
        final data = jsonDecode(cachedJson) as Map<String, dynamic>;
        return UserModel.fromJson(data);
      }
    } catch (_) {
      // Ignore cache reading failure
    }
    return null;
  }

  Future<UserModel> updateProfile({
    required String token,
    String? fullName,
    String? email,
    String? phoneNumber,
  }) async {
    final url = Uri.parse('${ApiConstants.baseUrl}/auth/me');

    final Map<String, dynamic> body = {};
    if (fullName != null) body['full_name'] = fullName.trim();
    if (email != null) body['email'] = email.trim();
    if (phoneNumber != null) body['phone_number'] = phoneNumber.trim();

    final response = await http.put(
      url,
      headers: {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer $token',
      },
      body: jsonEncode(body),
    );

    if (response.statusCode == 200) {
      final data = jsonDecode(response.body) as Map<String, dynamic>;
      final user = UserModel.fromJson(data);
      await _cacheUser(response.body);
      return user;
    } else {
      final errorData = jsonDecode(response.body);
      throw Exception(
        errorData is Map && errorData['detail'] != null
            ? errorData['detail'].toString()
            : 'Failed to update profile',
      );
    }
  }

  Future<UserModel> uploadAvatar({
    required String token,
    required List<int> bytes,
    required String filename,
  }) async {
    final url = Uri.parse('${ApiConstants.baseUrl}/auth/me/avatar');

    final request = http.MultipartRequest('POST', url);
    request.headers['Authorization'] = 'Bearer $token';

    request.files.add(
      http.MultipartFile.fromBytes(
        'file',
        bytes,
        filename: filename,
      ),
    );

    final streamedResponse = await request.send();
    final response = await http.Response.fromStream(streamedResponse);

    if (response.statusCode == 200) {
      final data = jsonDecode(response.body) as Map<String, dynamic>;
      final user = UserModel.fromJson(data);
      await _cacheUser(response.body);
      return user;
    } else {
      try {
        final errorData = jsonDecode(response.body);
        throw Exception(
          errorData is Map && errorData['detail'] != null
              ? errorData['detail'].toString()
              : 'Failed to upload profile photo',
        );
      } catch (e) {
        if (e is Exception) rethrow;
        throw Exception('Failed to upload profile photo (${response.statusCode})');
      }
    }
  }

  Future<UserModel> deleteAvatar({required String token}) async {
    final url = Uri.parse('${ApiConstants.baseUrl}/auth/me/avatar');

    final response = await http.delete(
      url,
      headers: {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer $token',
      },
    );

    if (response.statusCode == 200) {
      final data = jsonDecode(response.body) as Map<String, dynamic>;
      final user = UserModel.fromJson(data);
      await _cacheUser(response.body);
      return user;
    } else {
      final errorData = jsonDecode(response.body);
      throw Exception(
        errorData is Map && errorData['detail'] != null
            ? errorData['detail'].toString()
            : 'Failed to remove profile photo',
      );
    }
  }

  Future<void> clearCache() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.remove(_cachedUserKey);
    } catch (_) {}
  }

  Future<void> _cacheUser(String userJson) async {
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString(_cachedUserKey, userJson);
    } catch (_) {}
  }
}

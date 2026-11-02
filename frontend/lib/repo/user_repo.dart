import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:http_parser/http_parser.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:mind_ai/const/api_constants.dart';
import 'package:mind_ai/model/user_model.dart';

class UserRepo {
  static const String _cachedUserKey = 'mindvault_cached_user_profile';

  static MediaType resolveImageMediaType(List<int> bytes, String filename) {
    // 1. Detect image type from binary magic bytes
    if (bytes.length >= 3 &&
        bytes[0] == 0xFF &&
        bytes[1] == 0xD8 &&
        bytes[2] == 0xFF) {
      return MediaType('image', 'jpeg');
    }

    if (bytes.length >= 4 &&
        bytes[0] == 0x89 &&
        bytes[1] == 0x50 && // P
        bytes[2] == 0x4E && // N
        bytes[3] == 0x47) { // G
      return MediaType('image', 'png');
    }

    if (bytes.length >= 12 &&
        bytes[0] == 0x52 &&
        bytes[1] == 0x49 &&
        bytes[2] == 0x46 &&
        bytes[3] == 0x46 && // RIFF
        bytes[8] == 0x57 &&
        bytes[9] == 0x45 &&
        bytes[10] == 0x42 &&
        bytes[11] == 0x50) { // WEBP
      return MediaType('image', 'webp');
    }

    // 2. Fallback to file extension
    final ext = filename.contains('.')
        ? filename.split('.').last.toLowerCase().trim()
        : '';

    if (ext == 'png') {
      return MediaType('image', 'png');
    }
    if (ext == 'webp') {
      return MediaType('image', 'webp');
    }
    if (ext == 'jpg' || ext == 'jpeg') {
      return MediaType('image', 'jpeg');
    }

    return MediaType('image', 'jpeg');
  }

  static String ensureValidImageFilename(String filename, MediaType mediaType) {
    final clean = filename.trim();
    final ext = clean.contains('.')
        ? clean.split('.').last.toLowerCase().trim()
        : '';
    final defaultExt = mediaType.subtype == 'png'
        ? 'png'
        : (mediaType.subtype == 'webp' ? 'webp' : 'jpg');

    if (ext == 'jpg' || ext == 'jpeg' || ext == 'png' || ext == 'webp') {
      return clean;
    }

    return clean.isEmpty ? 'avatar.$defaultExt' : '$clean.$defaultExt';
  }

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

    final mediaType = resolveImageMediaType(bytes, filename);
    final safeFilename = ensureValidImageFilename(filename, mediaType);

    final request = http.MultipartRequest('POST', url);
    request.headers['Authorization'] = 'Bearer $token';

    request.files.add(
      http.MultipartFile.fromBytes(
        'file',
        bytes,
        filename: safeFilename,
        contentType: mediaType,
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

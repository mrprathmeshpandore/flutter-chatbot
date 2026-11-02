import 'package:flutter_test/flutter_test.dart';
import 'package:mind_ai/main.dart';

void main() {
  testWidgets('MindVault AI app renders welcome screen', (WidgetTester tester) async {
    await tester.pumpWidget(const MyApp());
    expect(find.text('MindVault AI'), findsWidgets);
  });
}

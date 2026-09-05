import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/features/forum/forum_errors.dart';
import 'package:plant_community_mobile/services/api_service.dart';

void main() {
  group('forumErrorMessage', () {
    test('a 400 surfaces the server\'s own sentence — the quote rejections '
        '(todo 342) reach the user verbatim', () {
      for (final sentence in const [
        'One of the quoted posts is not available.',
        'A post may quote at most 3 other posts.',
        'A quote may be at most 1000 characters.',
      ]) {
        expect(
          forumErrorMessage(
            ApiException(sentence, statusCode: 400),
            fallback: 'Could not post your reply.',
          ),
          sentence,
        );
      }
    });

    test('an empty 400 message falls back rather than showing nothing', () {
      expect(
        forumErrorMessage(
          ApiException('', statusCode: 400),
          fallback: 'Could not post your reply.',
        ),
        'Could not post your reply.',
      );
    });

    test('429 is the shared rate-limit line; 403 the action notice; 5xx, '
        'network and non-API errors the fallback', () {
      expect(
        forumErrorMessage(
          ApiException('slow down', statusCode: 429),
          fallback: 'f',
        ),
        forumRateLimitedMessage,
      );
      expect(
        forumErrorMessage(
          ApiException('denied', statusCode: 403),
          fallback: 'f',
          forbidden: 'Sign in to reply.',
        ),
        'Sign in to reply.',
      );
      expect(
        forumErrorMessage(
          ApiException('server down', statusCode: 503),
          fallback: 'f',
        ),
        'f',
      );
      expect(forumErrorMessage(ApiException('offline'), fallback: 'f'), 'f');
      expect(forumErrorMessage(StateError('x'), fallback: 'f'), 'f');
    });
  });
}

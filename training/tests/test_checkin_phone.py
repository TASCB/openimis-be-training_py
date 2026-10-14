from django.test import SimpleTestCase

from training.services import normalize_phone, _normalized_phone_data


class NormalizePhoneTest(SimpleTestCase):
    def test_same_number_in_every_format(self):
        for raw in ['0712345678', '712345678', '712 345 678', '+255712345678', '255 712 345 678', '+255-712-345-678']:
            self.assertEqual(normalize_phone(raw), '0712345678', raw)

    def test_airtel_and_halotel_prefixes(self):
        self.assertEqual(normalize_phone('0687654321'), '0687654321')
        self.assertEqual(normalize_phone('621000111'), '0621000111')

    def test_rejects_non_mobile_numbers(self):
        for raw in ['', None, '123', '0222123456', '07123456789', 'abc', '+2557123']:
            self.assertIsNone(normalize_phone(raw), raw)


class RegisterPhoneTest(SimpleTestCase):
    def test_mobile_numbers_are_normalised(self):
        self.assertEqual(_normalized_phone_data({'phone': '+255 712 345 678'})['phone'], '0712345678')

    def test_other_numbers_are_kept_as_typed(self):
        data = {'phone': '+44 20 7946 0958', 'full_name': 'Guest'}
        self.assertIs(_normalized_phone_data(data), data)
        self.assertEqual(_normalized_phone_data({'full_name': 'No phone'}), {'full_name': 'No phone'})

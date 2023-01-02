import xlsxwriter


class BaseXLSXRenderer:
    labels = {}
    workbook_options = {}

    def render(self, file, data, *args, **kwargs):
        workbook = xlsxwriter.Workbook(file, self.workbook_options)
        worksheet = workbook.add_worksheet('sheet 1')

        bold = workbook.add_format({'bold': True})

        if data:
            if self.labels:
                header = [self.labels[key] for key in data[0].keys()]
            else:
                header = list(data[0].keys())

            for col, label in enumerate(header):
                worksheet.write(0, col, label, bold)
            row_idx = 1
            for row in data:
                for col_idx, (key, value) in enumerate(row.items()):
                    worksheet.write(row_idx, col_idx, value)
                row_idx += 1

        workbook.close()

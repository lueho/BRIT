import xlsxwriter


class BaseXLSXRenderer:
    labels = {}
    workbook_options = {}
    column_order = []

    def render(self, file, data, *args, **kwargs):
        workbook = xlsxwriter.Workbook(file, self.workbook_options)
        worksheet = workbook.add_worksheet('sheet 1')

        bold = workbook.add_format({'bold': True})

        if data:
            # Define the header row
            if not self.column_order:
                if self.labels:
                    self.column_order = list(self.labels.keys())
                else:
                    self.column_order = list(data[0].keys())
            if self.labels:
                header = [self.labels[col] for col in self.column_order]
            else:
                header = self.column_order

            # reorder columns in the data to match the given header row
            data = [dict((k, row.get(k)) for k in self.column_order)  for row in data]

            for col, label in enumerate(header):
                worksheet.write(0, col, label, bold)
            row_idx = 1
            for row in data:
                for col_idx, (key, value) in enumerate(row.items()):
                    worksheet.write(row_idx, col_idx, value)
                row_idx += 1

        workbook.close()

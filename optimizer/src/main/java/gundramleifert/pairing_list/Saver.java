package gundramleifert.pairing_list;

import gundramleifert.pairing_list.configs.BoatConfig;
import gundramleifert.pairing_list.configs.DisplayConfig;
import gundramleifert.pairing_list.configs.ScheduleConfig;
import gundramleifert.pairing_list.types.Schedule;
import lombok.SneakyThrows;

import java.io.File;
import java.io.IOException;
import java.util.Random;
import java.util.function.Consumer;

public class Saver implements Consumer<Schedule> {
    private String outPdfValue;
    private String outYamlValue;
    private String outCsvValue;
    private DisplayConfig displayProps;
    private ScheduleConfig scheduleProps;

    public Saver(String outPdfValue, String outYamlValue, String outCsvValue, DisplayConfig displayProps, ScheduleConfig scheduleProps) {
        this.outPdfValue = outPdfValue;
        this.outYamlValue = outYamlValue;
        this.outCsvValue = outCsvValue;
        this.displayProps = displayProps;
        this.scheduleProps = scheduleProps;
    }

    @Override
    @SneakyThrows
    public void accept(Schedule schedule) {
        if (outPdfValue != null) {
            String[] titles = scheduleProps.titles;
            if (outCsvValue!=null){
                schedule.writeCSV(new File(outCsvValue));
            }
            if (outYamlValue!=null){
                schedule.writeYaml(new File(outYamlValue));
            }
            for (int i = 0; i < titles.length; i++) {
                String outNamePdf = titles.length == 1 ? outPdfValue : outPdfValue.replace(".pdf", "_" + i + ".pdf");
                String title = titles[i];
                String[] teamsIntern = scheduleProps.teams;
                // System.arraycopy(scheduleProps.teams,0,teamsIntern,0,teamsIntern.length);
                // rotate all teams by one
                if (i > 0) {
                    String remember = teamsIntern[0];
                    for (int j = 0; j < teamsIntern.length - 1; j++) {
                        teamsIntern[j] = teamsIntern[j + 1];
                    }
                    teamsIntern[teamsIntern.length - 1] = remember;
                }
                try {
                    Yaml.dftMapper().writeValue(new File(outNamePdf.replace(".pdf","_teams.yml")),scheduleProps.teams);
                } catch (IOException e) {
                    throw new RuntimeException(e);
                }

                new PdfCreator(displayProps, scheduleProps, new File(outNamePdf))
                        .create(schedule, title, new Random(1234), false);
                File fileDebug = new File(outNamePdf.replace(".pdf", "_debug.pdf"));
                new PdfCreator(displayProps, scheduleProps, fileDebug)
                        .create(schedule, title, new Random(1234), true);
            }
        }

    }
}

package gundramleifert.pairing_list;

import com.itextpdf.kernel.colors.ColorConstants;
import com.itextpdf.kernel.colors.DeviceGray;
import com.itextpdf.kernel.font.PdfFont;
import com.itextpdf.kernel.font.PdfFontFactory;
import com.itextpdf.kernel.geom.PageSize;
import com.itextpdf.kernel.pdf.PdfDocument;
import com.itextpdf.kernel.pdf.PdfDocumentInfo;
import com.itextpdf.kernel.pdf.PdfWriter;
import com.itextpdf.layout.Document;
import com.itextpdf.layout.borders.Border;
import com.itextpdf.layout.element.*;
import com.itextpdf.layout.properties.TextAlignment;
import com.itextpdf.layout.properties.VerticalAlignment;
import gundramleifert.pairing_list.configs.BoatConfig;
import gundramleifert.pairing_list.configs.DisplayConfig;
import gundramleifert.pairing_list.configs.ScheduleConfig;
import gundramleifert.pairing_list.cost_calculators.CostCalculatorBoatSchedule;
import gundramleifert.pairing_list.types.*;
import lombok.SneakyThrows;

import java.io.File;
import java.io.FileNotFoundException;
import java.io.IOException;
import java.util.*;
import java.util.List;
import java.util.stream.Collectors;

public class PdfCreator implements AutoCloseable {

    private final DisplayConfig displayConfig;
    private final ScheduleConfig scheduleConfig;
    private final File outFile;
    private Document doc;
    private boolean isEmptyPage = true;
    private DisplayConfig.DeviceRgbWithAlpha[] bgColors;
    private PdfFont font;

    private static Map<String, DisplayConfig.DeviceRgbWithAlpha> createColorMap(DisplayConfig displayConfig) {
        Map<String, DisplayConfig.DeviceRgbWithAlpha> res = defaultColorMap();
        if (displayConfig.additional_colors == null || displayConfig.additional_colors.isEmpty()) {
            return res;
        }
        for (String name : displayConfig.additional_colors.keySet()) {
            if (!name.toUpperCase().equals(name)) {
                throw new RuntimeException(String.format("color name %s is not upper.", name));
            }
            int[] rgba = displayConfig.additional_colors.get(name);
            res.put(name, DisplayConfig.DeviceRgbWithAlpha.fromArray(rgba));
        }
        return res;
    }

    private static Map<String, DisplayConfig.DeviceRgbWithAlpha> defaultColorMap() {
        HashMap<String, DisplayConfig.DeviceRgbWithAlpha> res = new HashMap<>();
        res.put("BLACK", DisplayConfig.DeviceRgbWithAlpha.fromArray(0));
        res.put("DARK_GRAY", DisplayConfig.DeviceRgbWithAlpha.fromArray(64));
        res.put("GRAY", DisplayConfig.DeviceRgbWithAlpha.fromArray(102));
        res.put("LIGHT_GRAY", DisplayConfig.DeviceRgbWithAlpha.fromArray(192));
        res.put("WHITE", DisplayConfig.DeviceRgbWithAlpha.fromArray(255));
        res.put("BLUE", DisplayConfig.DeviceRgbWithAlpha.fromArray(0, 0, 255));
        res.put("CYAN", DisplayConfig.DeviceRgbWithAlpha.fromArray(0, 255, 255));
        res.put("GREEN", DisplayConfig.DeviceRgbWithAlpha.fromArray(106, 168, 79));
        res.put("ORANGE", DisplayConfig.DeviceRgbWithAlpha.fromArray(255, 153, 0));
        res.put("PINK", DisplayConfig.DeviceRgbWithAlpha.fromArray(195, 44, 195));
        res.put("RED", DisplayConfig.DeviceRgbWithAlpha.fromArray(255, 0, 0));
        res.put("YELLOW", DisplayConfig.DeviceRgbWithAlpha.fromArray(255, 255, 0));
        res.put("HELLBLAU", DisplayConfig.DeviceRgbWithAlpha.fromArray(0, 167, 226));
        res.put("DUNKELBLAU", DisplayConfig.DeviceRgbWithAlpha.fromArray(0, 0, 139));

        res.put("LIGHTBLUE", res.get("HELLBLAU"));
        res.put("DARKBLUE", res.get("DUNKELBLAU"));
        res.put("GELB", res.get("YELLOW"));
        res.put("LILA", res.get("PINK"));
        res.put("GRUEN", res.get("GREEN"));
        res.put("GREY", res.get("GRAY"));
        res.put("GRAU", res.get("GRAY"));
        res.put("SCHWARZ", res.get("BLACK"));
        res.put("WEISS", res.get("WHITE"));
        res.put("BLAU", res.get("BLUE"));
        res.put("ROT", res.get("RED"));
        return res;
    }

    private static float avg(DisplayConfig.DeviceRgbWithAlpha color) {
        float[] f = color.getColorValue();
        float res = 0;
        for (float v : f) {
            res += v;
        }
        return res / f.length;
    }

    public PdfCreator(DisplayConfig displayConfig,
                      ScheduleConfig scheduleConfig,
                      File outFile) {
        this.displayConfig = displayConfig;
        this.scheduleConfig = scheduleConfig;
        this.outFile = outFile;
    }

    public void init() {
        init(null);
    }

    public void init(String title) {
        try {
            font = PdfFontFactory.createFont(displayConfig.font);
        } catch (IOException e) {
            throw new RuntimeException(String.format("cannot find font '%s'", displayConfig.font), e);
        }
        PdfWriter writer;
        try {
            writer = new PdfWriter(this.outFile);
        } catch (FileNotFoundException e) {
            throw new RuntimeException(e);
        }
        PageSize pageSize = PageSize.A4;
        if (displayConfig.landscape) {
            pageSize = pageSize.rotate();
        }
        this.doc = new Document(new PdfDocument(writer), pageSize);
        PdfDocumentInfo documentInfo = doc.getPdfDocument().getDocumentInfo();
        if (title != null) {
            documentInfo.setTitle(title);
        }
        String creator = "https://github.com/gundramleifert/PairingList";
        String cwd = new File(".").getAbsoluteFile().getParent();
        if (cwd.contains("PairingList") && !cwd.contains("Test")) {
            creator = creator.replace("PairingList", cwd.substring(cwd.indexOf("PairingList")));
        }
        documentInfo.setCreator(creator);
        documentInfo.setAuthor("Gundram Leifert");
        documentInfo.setSubject("Pairing List");
        doc.setBottomMargin(10.0f);
        doc.setTopMargin(10.0f);
        BoatConfig[] boats = scheduleConfig.boats;
        this.bgColors = new DisplayConfig.DeviceRgbWithAlpha[boats.length];
        Map<String, DisplayConfig.DeviceRgbWithAlpha> colorMap = createColorMap(displayConfig);
        for (int i = 0; i < boats.length; i++) {
            String color_bg = boats[i].color;
            if (color_bg == null)
                color_bg = displayConfig.headercolor_default;
            DisplayConfig.DeviceRgbWithAlpha color = colorMap.get(color_bg.toUpperCase());
            if (color == null) {
                throw new RuntimeException(String.format("cannot interpret key `%s` - choose one of %s",
                        color_bg,
                        String.join(",", colorMap.keySet())));
            }
            bgColors[i] = color;
        }
    }


    private Cell getDft(int row, int col) {
        return new Cell(row, col)
                .setPadding(0.0f)
                .setFontSize(displayConfig.fontsize);
    }
    
    private Cell getCell(String text, int row, int col) {
        return getDft(row, col)
                .add(new Paragraph(new Text(text).setFont(font)))
                .setPadding(0.0f)
                .setTextAlignment(TextAlignment.CENTER)
                .setVerticalAlignment(VerticalAlignment.MIDDLE);
    }

    private Cell getCell(String text) {
        return getCell(text, 1, 1);
    }

    private static void underlineText(Cell cell) {
        cell.getChildren().forEach(iElement -> {
            if (iElement instanceof Paragraph) {
                ((Paragraph) iElement).setUnderline();
            }
        });
    }

    private static void boldText(Cell cell) {
        cell.getChildren().forEach(iElement -> {
            if (iElement instanceof Paragraph) {
                ((Paragraph) iElement).setBold();
            }
        });
    }

    private Cell getCell(String text, int index) {
        return getCell(text, index, 1.0f);
    }

    private Cell getCell(String text, int index, float opacity) {
        return getCell(text, index >= 0 ? bgColors[index] : null, opacity);
    }

    private Cell getCell(String text, DisplayConfig.DeviceRgbWithAlpha bgColor, float opacity) {
        Cell cell = getCell(text);
        if (bgColor != null) {
            float v = (1 - (1 - avg(bgColor)) * bgColor.alpha * opacity);
            DisplayConfig.DeviceRgbWithAlpha fg = v > 0.5f ? DisplayConfig.DeviceRgbWithAlpha.BLACK : DisplayConfig.DeviceRgbWithAlpha.WHITE;
            cell.setBackgroundColor(bgColor, bgColor.alpha * opacity)
                    .setFontColor(fg);
        }
        return cell;
    }

    private Cell getCellSep(int colspan, float height) {
        return getDft(1, colspan)
                .setHeight(height)
                .setBorder(Border.NO_BORDER);
    }

    private Cell getCellSpan(String text, int rowspan) {
        return getDft(rowspan, 1)
                .add(new Paragraph(new Text(text).setFont(font)))
                .setTextAlignment(TextAlignment.CENTER)
                //.setBorderBottom(new DoubleBorder(1.0f))
                .setVerticalAlignment(VerticalAlignment.MIDDLE);
    }

    public void newPage(boolean alsoIfEmpty) {
        if (alsoIfEmpty || !isEmptyPage) {
            doc.add(new AreaBreak());
            isEmptyPage = true;
        }
    }

    private static int sum(int[] vec) {
        int res = vec[0];
        for (int i = 1; i < vec.length; i++) {
            res += vec[i];
        }
        return res;
    }

    public PdfCreator createScheduleDistribution(Schedule schedule, boolean sortBoats) {
        newPage(false);
        MatchMatrix matchMatrix = new MatchMatrix(scheduleConfig.numTeams, scheduleConfig.numBoats);
        int[][] values = new int[scheduleConfig.flights][scheduleConfig.flights + 1];
        for (int i = 0; i < schedule.size(); i++) {
            Flight flight = schedule.get(i);
            matchMatrix.add(flight, sortBoats);
            int[] matchDistribution = matchMatrix.getMatchDistribution();
            System.arraycopy(matchDistribution, 0, values[i], 0, matchDistribution.length);
        }
        int[] matchDistribution = matchMatrix.getMatchDistribution();
        int columns = 0;
        for (int i = 0; i < matchDistribution.length; i++) {
            if (matchDistribution[i] > 0) {
                columns = i + 2;
            }
        }
        float[] columnWidths = new float[columns];
        Arrays.fill(columnWidths, displayConfig.width / columns);
        Table table = new Table(columnWidths);
        table.addCell(getCell(""));
        table.addCell(getCell("number of matches", 1, columns - 1));
        table.addCell(getCell("flight"));
        for (int i = 0; i < columns - 1; i++) {
            table.addCell(getCell(String.valueOf(i)));
        }
        for (int flightIdx = 0; flightIdx < values.length; flightIdx++) {
            int[] valuesFlight = values[flightIdx];
            float max = sum(matchDistribution);
            table.addCell(getCell(String.valueOf(flightIdx + 1)));
            for (int row = 0; row < columns - 1; row++) {
                int cnt = valuesFlight[row];
                float weight = 1 - cnt / max;
                Cell cell = getCell(cnt == 0 ? "" : String.valueOf(cnt));
                if (weight < 0.5) {
                    cell.setFontColor(ColorConstants.WHITE);
                }
                cell.setBackgroundColor(new DeviceGray(weight));
                table.addCell(cell);
            }
        }
        doc.add(table);
        isEmptyPage = false;
        return this;
    }

    private static String toString(String[] teams, List<Byte> lst) {
        return lst
                .stream()
                .map(aByte -> teams[aByte].trim())
                .filter(s -> !s.isEmpty())
                .collect(Collectors.joining(" | "));
    }

    public void create(Schedule schedule, String title, Random random, boolean debug) {
        init();
        if (debug) {
            createScheduleDistribution(schedule, true);
            createBoatDistribution(schedule);
            createShuttleDistribution(schedule);
        }
        createSchedule(schedule, title, (byte) -1, null);
        if (displayConfig.teamwise_list) {
            Map<Race, SameShuttle> sameShuttles = Util.teamsOnSameShuttles(schedule, random);

            for (byte i = 0; i < scheduleConfig.teams.length; i++) {
                createSchedule(schedule, title, i, sameShuttles);
            }
        }
        close();
    }

    public PdfCreator createBoatDistribution(Schedule schedule) {
        newPage(false);
        BoatMatrix matchMatrix = new BoatMatrix(scheduleConfig);
        int[][] values = new int[schedule.size()][];
        for (int flightIdx = 0; flightIdx < schedule.size(); flightIdx++) {
            Flight flight = schedule.get(flightIdx);
            matchMatrix.add(flight);
            values[flightIdx] = matchMatrix.getBoatDistribution();
        }
        int[] matchDistribution = values[schedule.size() - 1];
        int columns = 0;
        for (int i = 0; i < matchDistribution.length; i++) {
            if (matchDistribution[i] > 0) {
                columns = i + 2;
            }
        }
        float[] columnWidths = new float[columns];
        Arrays.fill(columnWidths, displayConfig.width / columns);
        Table table = new Table(columnWidths);
        table.setVerticalBorderSpacing(10f);
        table.addCell(getCell(""));
        table.addCell(getCell("number of boat usages", 1, columns - 1));
        table.addCell(getCell("flight"));
        for (int i = 0; i < columns - 1; i++) {
            table.addCell(getCell(String.valueOf(i)));
        }
        for (int flightIdx = 0; flightIdx < values.length; flightIdx++) {
            int[] valuesFlight = values[flightIdx];
            float max = sum(matchDistribution);
            table.addCell(getCell(String.valueOf(flightIdx + 1)));
            for (int row = 0; row < columns - 1; row++) {
                int cnt = row < valuesFlight.length ? valuesFlight[row] : 0;
                float weight = 1 - cnt / max;
                Cell cell = getCell(cnt == 0 ? "" : String.valueOf(cnt));
                if (weight < 0.5) {
                    cell.setFontColor(ColorConstants.WHITE);
                }
                cell.setBackgroundColor(new DeviceGray(weight));
                table.addCell(cell);
            }
        }
        doc.add(table);
        isEmptyPage = false;
        return this;
    }

    public PdfCreator createShuttleDistribution(Schedule schedule) {
        newPage(false);
        String[] clubs = scheduleConfig.teams;
        float[] columnWidths = new float[5];
        Arrays.fill(columnWidths, displayConfig.width / 5);
        Table table = new Table(columnWidths);
        table.setVerticalBorderSpacing(10f);
        Arrays.asList("At Flight", "On Boat", "On Water 1", "On Water 2", "Boatchange")
                .forEach(s -> table.addCell(getCell(s)));
        table.addCell(getCellSep(5, 0.3f));
        for (int i = 1; i < schedule.size(); i++) {
            InterFlightStat interFlightStat =
                    CostCalculatorBoatSchedule.getInterFlightStat(schedule.get(i - 1), schedule.get(i), scheduleConfig.numTeams);
            table.addCell(getCell(String.format("%d -> %d", i, i + 1)));
            table.addCell(getCell(toString(clubs, interFlightStat.teamsStayOnBoat)));
            table.addCell(getCell(toString(clubs, interFlightStat.teamsAtWaterAtLastRace)));
            table.addCell(getCell(toString(clubs, interFlightStat.teamsAtWaterAtFirstRace)));
            table.addCell(getCell(toString(clubs, interFlightStat.teamsChangeBoats)));
        }
        doc.add(table);
        isEmptyPage = false;
        return this;
    }

    private float getOpacity(byte teamCurrent, byte teamToHighlight, SameShuttle sameShuttles) {
        if (teamToHighlight < 0) {
            return this.displayConfig.opacity_default;
        }
        if (teamCurrent == teamToHighlight) {
            return displayConfig.opacity_active;
        }
        if (sameShuttles != null) {
            if (!sameShuttles.boats.contains(teamToHighlight)) {
                return displayConfig.opacity_inactive;
            }
            if (sameShuttles.boats.contains(teamCurrent)) {
                return displayConfig.opacity_same_shuttle;
            }
        }
        return displayConfig.opacity_inactive;
    }

    private boolean sameShuttle(byte teamCurrent, byte teamToHighlight, SameShuttle sameShuttles) {
        if (teamToHighlight < 0) {
            return false;
        }
        if (teamCurrent == teamToHighlight) {
            return true;
        }
        if (sameShuttles != null) {
            if (!sameShuttles.boats.contains(teamToHighlight)) {
                return false;
            }
            if (sameShuttles.boats.contains(teamCurrent)) {
                return true;
            }
        }
        return false;
    }

    @SneakyThrows
    public PdfCreator createSchedule(
            Schedule schedule,
            String title,
            byte teamIndex,
            Map<Race, SameShuttle> sameShuttles) {
        newPage(false);
        float[] columnWidths = new float[scheduleConfig.numBoats + 2];
        double basewith = displayConfig.width / (scheduleConfig.numBoats + 2 * displayConfig.factor_flight_race_width);
        Arrays.fill(columnWidths, 2, columnWidths.length, (float) basewith);
        Arrays.fill(columnWidths, 0, 2, (float) (basewith * displayConfig.factor_flight_race_width));
        Table table = new Table(columnWidths);
        table.addCell(getCell("Flight", -1));
        table.addCell(getCell("Race", -1));
        int default_index = 1;
        for (int i = 0; i < scheduleConfig.numBoats; i++) {
            String name = this.scheduleConfig.boats[i].name;
            if (name == null || name.isEmpty()) {
                name = String.format("Boat %d", default_index++);
            }
            table.addCell(getCell(name, i));
        }
        int race = 1;
        String[] clubs = scheduleConfig.teams;
        DisplayConfig.DeviceRgbWithAlpha LIGHT_GRAY = null;
        if (displayConfig.same_boat_color != null && displayConfig.same_boat_color.length > 1) {
            LIGHT_GRAY = DisplayConfig.DeviceRgbWithAlpha.fromArray(displayConfig.same_boat_color);
        }
        DisplayConfig.DeviceRgbWithAlpha DARK_GRAY = DisplayConfig.DeviceRgbWithAlpha.fromArray(100);
        for (int flight = 0; flight < schedule.size(); flight++) {
            table.addCell(getCellSep(columnWidths.length, 1.0f));
            Flight f = schedule.get(flight);
            table.addCell(getCellSpan(String.valueOf(flight + 1), f.races.length));
            for (int i = 0; i < f.races.length; i++) {
                table.addCell(getCell(String.valueOf(race++), -1));
                Race r = f.races[i];
                int col = 0;
                for (; col < r.teams.length; col++) {
                    byte team = r.teams[col];
                    String teamName = clubs[team];
                    if (teamName.isEmpty()) {
                        teamName = this.displayConfig.name_empty_boat;
                    }
//                    float opacity = getOpacity(team,
//                            teamIndex,
//                            sameShuttles == null ? null : sameShuttles.get(r)
//                    );
                    boolean sameS = sameShuttles != null && sameShuttle(team, teamIndex, sameShuttles.get(r));
                    DisplayConfig.DeviceRgbWithAlpha bg = team == teamIndex ? DARK_GRAY : sameS ? LIGHT_GRAY : null;
                    Cell cell = getCell(teamName, bg, 1.0f);
//                    if (sameS){
//                        underlineText(cell);
//                        boldText(cell);
//                    }
//                    if (opacity==displayProps.opacity_same_shuttle){
//                        underlineText(cell);
//                        cell.setBackgroundColor(bgColors[col]);
//                    }
                    table.addCell(cell);
                }
                while (col < scheduleConfig.numBoats) {
                    //add empty cell
                    table.addCell(getCell("", col++));
                }
            }
        }
        doc.add(new Paragraph(new Text(title).setFont(font))
                .setFontSize(displayConfig.fontsize * 2)
                .setTextAlignment(TextAlignment.CENTER)
        );
        if (teamIndex >= 0) {
            doc.add(new Paragraph(new Text(scheduleConfig.teams[teamIndex]).setFont(font))
                    .setFontSize(displayConfig.fontsize * 1.5f)
                    .setTextAlignment(TextAlignment.CENTER)
            );
        }
        doc.add(table);
        isEmptyPage = false;
        return this;
    }

    @SneakyThrows
    public void close() {
        this.doc.close();
    }
}
